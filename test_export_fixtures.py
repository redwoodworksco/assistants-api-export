#!/usr/bin/env python3
"""
Fixture tests for export_assistants_api.py — specifically the RUN / RUN-STEP
export path, which cannot be verified live without creating a run (a model
invocation, i.e. money). Fixtures are constructed from the official API
reference object shapes:
  - run:      https://developers.openai.com/api/docs/api-reference/runs/object
  - run step: https://developers.openai.com/api/docs/api-reference/run-steps/step-object

Run:  python3 test_export_fixtures.py
"""

import json
import sys
import unittest

from export_assistants_api import (
    NotFoundError, collect_file_ids, export_thread, paginate,
)

THREAD_ID = "thread_fix001"
RUN_ID = "run_fix001"

FIXTURE_THREAD = {
    "id": THREAD_ID,
    "object": "thread",
    "created_at": 1699012949,
    "metadata": {},
    "tool_resources": {},
}

FIXTURE_MESSAGES_PAGE1 = {
    "object": "list",
    "data": [
        {
            "id": "msg_fix001",
            "object": "thread.message",
            "created_at": 1699017614,
            "thread_id": THREAD_ID,
            "role": "user",
            "content": [
                {"type": "text",
                 "text": {"value": "Plot my data", "annotations": []}}
            ],
            "attachments": [
                {"file_id": "file-msgattach1",
                 "tools": [{"type": "code_interpreter"}]}
            ],
            "assistant_id": None, "run_id": None, "metadata": {},
        }
    ],
    "first_id": "msg_fix001", "last_id": "msg_fix001", "has_more": True,
}

FIXTURE_MESSAGES_PAGE2 = {
    "object": "list",
    "data": [
        {
            "id": "msg_fix002",
            "object": "thread.message",
            "created_at": 1699017620,
            "thread_id": THREAD_ID,
            "role": "assistant",
            "content": [
                {"type": "image_file",
                 "image_file": {"file_id": "file-imgout1"}},
                {"type": "text",
                 "text": {
                     "value": "Here is the plot [source]",
                     "annotations": [
                         {"type": "file_path",
                          "text": "sandbox:/mnt/data/plot.png",
                          "file_path": {"file_id": "file-pathann1"},
                          "start_index": 13, "end_index": 21}
                     ]}}
            ],
            "attachments": [],
            "assistant_id": "asst_fix001", "run_id": RUN_ID, "metadata": {},
        }
    ],
    "first_id": "msg_fix002", "last_id": "msg_fix002", "has_more": False,
}

# Run object per API reference (runs/object)
FIXTURE_RUNS = {
    "object": "list",
    "data": [
        {
            "id": RUN_ID,
            "object": "thread.run",
            "created_at": 1699017615,
            "assistant_id": "asst_fix001",
            "thread_id": THREAD_ID,
            "status": "completed",
            "started_at": 1699017615,
            "expires_at": None,
            "cancelled_at": None,
            "failed_at": None,
            "completed_at": 1699017619,
            "last_error": None,
            "model": "gpt-4o",
            "instructions": None,
            "incomplete_details": None,
            "tools": [{"type": "code_interpreter"}],
            "metadata": {},
            "usage": {"prompt_tokens": 123, "completion_tokens": 456,
                      "total_tokens": 579},
            "temperature": 1.0, "top_p": 1.0,
            "max_prompt_tokens": 1000, "max_completion_tokens": 1000,
            "truncation_strategy": {"type": "auto",
                                    "last_messages": None},
            "response_format": "auto", "tool_choice": "auto",
            "parallel_tool_calls": True,
        }
    ],
    "first_id": RUN_ID, "last_id": RUN_ID, "has_more": False,
}

# Run-step objects per API reference (run-steps/step-object):
# one message_creation step + one tool_calls (code_interpreter) step
FIXTURE_STEPS = {
    "object": "list",
    "data": [
        {
            "id": "step_fix001",
            "object": "thread.run.step",
            "created_at": 1699017616,
            "run_id": RUN_ID,
            "assistant_id": "asst_fix001",
            "thread_id": THREAD_ID,
            "type": "tool_calls",
            "status": "completed",
            "cancelled_at": None, "completed_at": 1699017617,
            "expired_at": None, "failed_at": None, "last_error": None,
            "step_details": {
                "type": "tool_calls",
                "tool_calls": [
                    {
                        "id": "call_fix001",
                        "type": "code_interpreter",
                        "code_interpreter": {
                            "input": "import matplotlib...",
                            "outputs": [
                                {"type": "image",
                                 "image": {"file_id": "file-stepimg1"}}
                            ],
                        },
                    }
                ],
            },
            "usage": {"prompt_tokens": 100, "completion_tokens": 50,
                      "total_tokens": 150},
        },
        {
            "id": "step_fix002",
            "object": "thread.run.step",
            "created_at": 1699017618,
            "run_id": RUN_ID,
            "assistant_id": "asst_fix001",
            "thread_id": THREAD_ID,
            "type": "message_creation",
            "status": "completed",
            "cancelled_at": None, "completed_at": 1699017619,
            "expired_at": None, "failed_at": None, "last_error": None,
            "step_details": {
                "type": "message_creation",
                "message_creation": {"message_id": "msg_fix002"},
            },
            "usage": {"prompt_tokens": 23, "completion_tokens": 6,
                      "total_tokens": 29},
        },
    ],
    "first_id": "step_fix001", "last_id": "step_fix002", "has_more": False,
}


def file_fixture(fid):
    return {"id": fid, "object": "file", "bytes": 12345,
            "created_at": 1699017610, "filename": fid + ".dat",
            "purpose": "assistants"}


class FakeClient:
    """Replays recorded fixtures keyed on (path, after-cursor)."""

    def __init__(self, missing_files=()):
        self.missing_files = set(missing_files)
        self.calls = []

    def get(self, path, params=None):
        params = params or {}
        self.calls.append((path, dict(params)))
        if path == "/threads/" + THREAD_ID:
            return FIXTURE_THREAD
        if path == "/threads/%s/messages" % THREAD_ID:
            if params.get("after") == "msg_fix001":
                return FIXTURE_MESSAGES_PAGE2
            return FIXTURE_MESSAGES_PAGE1
        if path == "/threads/%s/runs" % THREAD_ID:
            return FIXTURE_RUNS
        if path == "/threads/%s/runs/%s/steps" % (THREAD_ID, RUN_ID):
            return FIXTURE_STEPS
        if path.startswith("/files/"):
            fid = path.split("/files/", 1)[1]
            if fid in self.missing_files:
                raise NotFoundError("Not found (HTTP 404) for GET " + path,
                                    status=404)
            return file_fixture(fid)
        raise AssertionError("Unexpected GET " + path)


ALL_EXPECTED_FILE_IDS = [
    "file-imgout1",    # image_file content part
    "file-msgattach1", # message attachment
    "file-pathann1",   # file_path annotation
    "file-stepimg1",   # code_interpreter image output in run step
]


class TestRunAndStepExport(unittest.TestCase):

    def test_full_thread_export_with_runs_and_steps(self):
        client = FakeClient()
        record, ok = export_thread(client, THREAD_ID, include_runs=True)
        self.assertTrue(ok)
        self.assertEqual(record["thread"]["id"], THREAD_ID)

        # messages: both pages, in order (pagination followed has_more/last_id)
        self.assertEqual([m["id"] for m in record["messages"]],
                         ["msg_fix001", "msg_fix002"])

        # runs: the run came through with API-reference fields intact
        self.assertEqual(len(record["runs"]), 1)
        run = record["runs"][0]
        self.assertEqual(run["id"], RUN_ID)
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["usage"]["total_tokens"], 579)

        # run steps: nested under the run, both types present
        self.assertEqual([s["id"] for s in run["steps"]],
                         ["step_fix001", "step_fix002"])
        self.assertEqual(run["steps"][0]["type"], "tool_calls")
        self.assertEqual(
            run["steps"][0]["step_details"]["tool_calls"][0]
               ["code_interpreter"]["outputs"][0]["image"]["file_id"],
            "file-stepimg1")
        self.assertEqual(run["steps"][1]["type"], "message_creation")

        # file metadata: all four reference points harvested
        self.assertEqual(sorted(record["files"].keys()),
                         ALL_EXPECTED_FILE_IDS)
        self.assertEqual(record["errors"], [])

        # record round-trips as JSON (portability check)
        rt = json.loads(json.dumps(record))
        self.assertEqual(rt["runs"][0]["steps"][1]["step_details"]
                         ["message_creation"]["message_id"], "msg_fix002")

    def test_file_id_collection_paths(self):
        record_client = FakeClient()
        record, _ = export_thread(record_client, THREAD_ID)
        ids = collect_file_ids(record["messages"], record["runs"])
        self.assertEqual(ids, ALL_EXPECTED_FILE_IDS)

    def test_deleted_file_recorded_not_fatal(self):
        client = FakeClient(missing_files={"file-stepimg1"})
        record, ok = export_thread(client, THREAD_ID)
        self.assertTrue(ok)
        self.assertNotIn("file-stepimg1", record["files"])
        errs = [e for e in record["errors"] if e["id"] == "file-stepimg1"]
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0]["error"], "not_found_or_expired")

    def test_deleted_thread_recorded_not_fatal(self):
        class Client404(FakeClient):
            def get(self, path, params=None):
                raise NotFoundError("Not found (HTTP 404)", status=404)
        record, ok = export_thread(Client404(), "thread_gone")
        self.assertFalse(ok)
        self.assertEqual(record["errors"][0]["error"], "not_found_or_deleted")

    def test_no_runs_flag(self):
        client = FakeClient()
        record, ok = export_thread(client, THREAD_ID, include_runs=False)
        self.assertTrue(ok)
        self.assertEqual(record["runs"], [])
        run_paths = [p for p, _ in client.calls if "/runs" in p]
        self.assertEqual(run_paths, [])

    def test_paginate_passes_cursor(self):
        client = FakeClient()
        items = list(paginate(client, "/threads/%s/messages" % THREAD_ID,
                              {"order": "asc"}))
        self.assertEqual(len(items), 2)
        # second call must carry after=msg_fix001
        second_call = client.calls[1]
        self.assertEqual(second_call[1].get("after"), "msg_fix001")


if __name__ == "__main__":
    unittest.main(verbosity=2)
