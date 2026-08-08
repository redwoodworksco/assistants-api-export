#!/usr/bin/env python3
"""
export_assistants_api.py — export your OpenAI Assistants API data to portable JSON
before the API is removed on August 26, 2026.

Exports: assistants, threads (by ID — the API cannot enumerate threads account-wide),
messages, runs, run steps, and attached-file METADATA (not file bytes) to one JSON
file per thread plus a manifest.

Works against both OpenAI (api.openai.com) and Azure OpenAI endpoints.

Requires: Python 3.8+ and the `requests` package (the only non-stdlib dependency).
    pip install requests

Auth:
    OpenAI:  export OPENAI_API_KEY=sk-...
    Azure:   export AZURE_OPENAI_API_KEY=...   (or reuse OPENAI_API_KEY)

Usage:
    # Export all assistants + two threads
    python3 export_assistants_api.py --out ./export \
        --thread-ids thread_abc123,thread_def456

    # Thread IDs from a file (one per line, '#' comments allowed)
    python3 export_assistants_api.py --out ./export --thread-file my_threads.txt

    # Azure OpenAI
    python3 export_assistants_api.py --out ./export \
        --azure-endpoint https://YOUR-RESOURCE.openai.azure.com \
        --api-version 2024-05-01-preview \
        --thread-file my_threads.txt

This script only performs GET requests (read-only). It never creates, modifies,
or deletes anything, and it never invokes a model (no runs are created).
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:  # pragma: no cover
    sys.stderr.write(
        "This script needs the 'requests' package: pip install requests\n"
    )
    sys.exit(1)

SCRIPT_VERSION = "1.0.0"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
PAGE_SIZE = 100
MAX_RETRIES = 6
BACKOFF_CAP_SECONDS = 60.0


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ApiError(Exception):
    """Base error for API failures."""

    def __init__(self, message, status=None, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


class AuthError(ApiError):
    pass


class NotFoundError(ApiError):
    pass


# ---------------------------------------------------------------------------
# HTTP client (OpenAI + Azure)
# ---------------------------------------------------------------------------

class Client:
    """Minimal read-only client for the Assistants API (OpenAI or Azure)."""

    def __init__(self, api_key, base_url=None, azure_endpoint=None,
                 api_version=None, session=None, sleep=time.sleep):
        if not api_key:
            raise AuthError(
                "No API key. Set OPENAI_API_KEY (or AZURE_OPENAI_API_KEY for "
                "--azure-endpoint) in your environment."
            )
        self.api_key = api_key
        self.azure = bool(azure_endpoint)
        self.api_version = api_version
        self._sleep = sleep
        if self.azure:
            if not api_version:
                raise ApiError(
                    "--api-version is required with --azure-endpoint "
                    "(e.g. 2024-05-01-preview)."
                )
            self.base_url = azure_endpoint.rstrip("/") + "/openai"
        else:
            self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.session = session or requests.Session()

    def _headers(self):
        if self.azure:
            return {"api-key": self.api_key}
        return {
            "Authorization": "Bearer " + self.api_key,
            "OpenAI-Beta": "assistants=v2",
        }

    def get(self, path, params=None):
        """GET with pagination-agnostic retry/backoff. Returns parsed JSON."""
        params = dict(params or {})
        if self.azure:
            params["api-version"] = self.api_version
        url = self.base_url + path
        last_err = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.get(
                    url, headers=self._headers(), params=params, timeout=60
                )
            except requests.RequestException as exc:
                last_err = ApiError("Network error for GET %s: %s" % (path, exc))
                self._sleep(self._backoff(attempt, None))
                continue

            if resp.status_code == 200:
                return resp.json()

            body = _safe_json(resp)
            message = _error_message(body) or resp.text[:300]

            if resp.status_code in (401, 403):
                raise AuthError(
                    "Authentication failed (HTTP %d) for GET %s: %s\n"
                    "Check that your API key is valid, has not been revoked, "
                    "and belongs to the right project/organization."
                    % (resp.status_code, path, message),
                    status=resp.status_code, body=body,
                )
            if resp.status_code == 404:
                raise NotFoundError(
                    "Not found (HTTP 404) for GET %s: %s" % (path, message),
                    status=404, body=body,
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                # Rate limit or transient server error: back off and retry.
                wait = self._backoff(attempt, resp.headers.get("Retry-After"))
                sys.stderr.write(
                    "  [retry] HTTP %d on %s — waiting %.1fs (attempt %d/%d)\n"
                    % (resp.status_code, path, wait, attempt + 1, MAX_RETRIES)
                )
                last_err = ApiError(
                    "HTTP %d for GET %s: %s" % (resp.status_code, path, message),
                    status=resp.status_code, body=body,
                )
                self._sleep(wait)
                continue

            raise ApiError(
                "HTTP %d for GET %s: %s" % (resp.status_code, path, message),
                status=resp.status_code, body=body,
            )
        raise last_err or ApiError("GET %s failed after %d retries" % (path, MAX_RETRIES))

    @staticmethod
    def _backoff(attempt, retry_after):
        if retry_after:
            try:
                return min(float(retry_after), BACKOFF_CAP_SECONDS)
            except ValueError:
                pass
        return min((2 ** attempt) + random.uniform(0, 1), BACKOFF_CAP_SECONDS)


def _safe_json(resp):
    try:
        return resp.json()
    except ValueError:
        return None


def _error_message(body):
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            return err.get("message")
        if isinstance(err, str):
            return err
    return None


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def paginate(client, path, params=None):
    """Yield every item from a cursor-paginated list endpoint."""
    params = dict(params or {})
    params.setdefault("limit", PAGE_SIZE)
    after = None
    while True:
        page_params = dict(params)
        if after:
            page_params["after"] = after
        page = client.get(path, params=page_params)
        items = page.get("data", [])
        for item in items:
            yield item
        if not page.get("has_more"):
            return
        after = page.get("last_id") or (items[-1]["id"] if items else None)
        if not after:
            return


# ---------------------------------------------------------------------------
# Export logic (transport-agnostic: takes any object with .get/paginate shape)
# ---------------------------------------------------------------------------

def export_assistants(client):
    """Return all assistants in the account/project (paginated)."""
    return list(paginate(client, "/assistants", {"order": "asc"}))


def collect_file_ids(messages, runs):
    """Pull every referenced file ID out of messages + runs."""
    file_ids = set()
    for msg in messages:
        for att in (msg.get("attachments") or []):
            fid = att.get("file_id")
            if fid:
                file_ids.add(fid)
        for part in (msg.get("content") or []):
            if part.get("type") == "image_file":
                fid = (part.get("image_file") or {}).get("file_id")
                if fid:
                    file_ids.add(fid)
            elif part.get("type") == "text":
                for ann in ((part.get("text") or {}).get("annotations") or []):
                    for key in ("file_citation", "file_path"):
                        fid = (ann.get(key) or {}).get("file_id")
                        if fid:
                            file_ids.add(fid)
    for run in runs:
        for step in (run.get("steps") or []):
            details = step.get("step_details") or {}
            for call in (details.get("tool_calls") or []):
                ci = call.get("code_interpreter") or {}
                for out in (ci.get("outputs") or []):
                    if out.get("type") == "image":
                        fid = (out.get("image") or {}).get("file_id")
                        if fid:
                            file_ids.add(fid)
    return sorted(file_ids)


def fetch_file_metadata(client, file_ids, errors):
    """Retrieve metadata for each file ID; record (not raise) missing files."""
    files = {}
    for fid in file_ids:
        try:
            files[fid] = client.get("/files/" + fid)
        except NotFoundError as exc:
            errors.append({
                "object": "file", "id": fid,
                "error": "not_found_or_expired", "detail": str(exc),
            })
        except AuthError:
            raise
        except ApiError as exc:
            errors.append({
                "object": "file", "id": fid, "error": "fetch_failed",
                "detail": str(exc),
            })
    return files


def export_thread(client, thread_id, include_runs=True):
    """
    Export one thread: thread object, all messages (ascending), all runs with
    their run steps, and metadata for every referenced file.

    Returns (record, ok). On a missing/deleted thread, record carries the error
    and ok is False.
    """
    record = {
        "export_schema": "assistants-thread-export/v1",
        "thread_id": thread_id,
        "exported_at": _now_iso(),
        "thread": None,
        "messages": [],
        "runs": [],
        "files": {},
        "errors": [],
    }
    try:
        record["thread"] = client.get("/threads/" + thread_id)
    except NotFoundError as exc:
        record["errors"].append({
            "object": "thread", "id": thread_id,
            "error": "not_found_or_deleted", "detail": str(exc),
        })
        return record, False

    record["messages"] = list(
        paginate(client, "/threads/%s/messages" % thread_id, {"order": "asc"})
    )

    if include_runs:
        for run in paginate(client, "/threads/%s/runs" % thread_id,
                            {"order": "asc"}):
            try:
                run["steps"] = list(paginate(
                    client,
                    "/threads/%s/runs/%s/steps" % (thread_id, run["id"]),
                    {"order": "asc"},
                ))
            except NotFoundError as exc:
                run["steps"] = []
                record["errors"].append({
                    "object": "run_steps", "id": run["id"],
                    "error": "not_found_or_expired", "detail": str(exc),
                })
            record["runs"].append(run)

    file_ids = collect_file_ids(record["messages"], record["runs"])
    record["files"] = fetch_file_metadata(client, file_ids, record["errors"])
    return record, True


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def read_thread_ids(args):
    ids = []
    if args.thread_ids:
        ids += [t.strip() for t in args.thread_ids.split(",") if t.strip()]
    if args.thread_file:
        with open(args.thread_file) as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    ids.append(line)
    # de-dupe, preserve order
    seen = set()
    out = []
    for tid in ids:
        if tid not in seen:
            seen.add(tid)
            out.append(tid)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Export OpenAI Assistants API data (assistants, threads, "
                    "messages, runs, run steps, file metadata) to JSON before "
                    "the August 26, 2026 shutdown.",
    )
    ap.add_argument("--out", default="./assistants-export",
                    help="Output directory (default: ./assistants-export)")
    ap.add_argument("--thread-ids", default="",
                    help="Comma-separated thread IDs to export")
    ap.add_argument("--thread-file", default=None,
                    help="File with one thread ID per line ('#' comments ok). "
                         "The API cannot list threads account-wide — you must "
                         "supply IDs from your own logs/DB (see README).")
    ap.add_argument("--no-assistants", action="store_true",
                    help="Skip exporting assistant objects")
    ap.add_argument("--no-runs", action="store_true",
                    help="Skip runs/run-steps (faster; messages only)")
    ap.add_argument("--base-url", default=None,
                    help="Override API base URL (default: %s)" % DEFAULT_BASE_URL)
    ap.add_argument("--azure-endpoint", default=None,
                    help="Azure OpenAI endpoint, e.g. "
                         "https://YOUR-RESOURCE.openai.azure.com")
    ap.add_argument("--api-version", default=None,
                    help="Azure api-version (required with --azure-endpoint), "
                         "e.g. 2024-05-01-preview")
    args = ap.parse_args(argv)

    api_key = os.environ.get("OPENAI_API_KEY")
    if args.azure_endpoint:
        api_key = os.environ.get("AZURE_OPENAI_API_KEY") or api_key

    try:
        client = Client(api_key, base_url=args.base_url,
                        azure_endpoint=args.azure_endpoint,
                        api_version=args.api_version)
    except ApiError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2

    thread_ids = read_thread_ids(args)
    if not thread_ids and args.no_assistants:
        sys.stderr.write(
            "Nothing to do: no thread IDs given and --no-assistants set.\n"
        )
        return 2

    outdir = args.out
    os.makedirs(os.path.join(outdir, "threads"), exist_ok=True)

    manifest = {
        "export_schema": "assistants-export-manifest/v1",
        "script_version": SCRIPT_VERSION,
        "exported_at": _now_iso(),
        "endpoint": "azure" if args.azure_endpoint else "openai",
        "base_url": client.base_url,
        "assistants_count": 0,
        "threads_requested": len(thread_ids),
        "threads_exported": 0,
        "threads_failed": [],
        "notes": [
            "The Assistants API cannot enumerate threads account-wide; "
            "only the thread IDs supplied were exported.",
            "files/ entries are metadata only — file CONTENT is not "
            "downloadable for assistants-purpose files via the API.",
        ],
    }

    try:
        if not args.no_assistants:
            print("Exporting assistants ...")
            assistants = export_assistants(client)
            manifest["assistants_count"] = len(assistants)
            _write_json(os.path.join(outdir, "assistants.json"), assistants)
            print("  %d assistant(s) -> assistants.json" % len(assistants))

        for tid in thread_ids:
            print("Exporting thread %s ..." % tid)
            record, ok = export_thread(client, tid,
                                       include_runs=not args.no_runs)
            _write_json(os.path.join(outdir, "threads", tid + ".json"), record)
            if ok:
                manifest["threads_exported"] += 1
                print("  %d message(s), %d run(s), %d file ref(s)%s"
                      % (len(record["messages"]), len(record["runs"]),
                         len(record["files"]),
                         (", %d warning(s)" % len(record["errors"]))
                         if record["errors"] else ""))
            else:
                manifest["threads_failed"].append(
                    {"thread_id": tid, "error": record["errors"][0]["error"]})
                print("  SKIPPED: %s" % record["errors"][0]["error"])
    except AuthError as exc:
        sys.stderr.write("\nerror: %s\n" % exc)
        return 2

    _write_json(os.path.join(outdir, "manifest.json"), manifest)
    print("\nDone. Manifest: %s" % os.path.join(outdir, "manifest.json"))
    if manifest["threads_failed"]:
        print("WARNING: %d thread(s) could not be exported (see manifest)."
              % len(manifest["threads_failed"]))
    return 0


def _write_json(path, obj):
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


if __name__ == "__main__":
    sys.exit(main())
