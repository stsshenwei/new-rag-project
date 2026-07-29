import tempfile
import time
import unittest
from pathlib import Path

from app.services.processing.processing_span_tracker import (
    SPAN_GENERATION,
    SPAN_SUBSPAN,
    ProcessingSpanRepository,
    ProcessingSpanTracker,
    STATUS_CANCELLED,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_RUNNING,
)


class ProcessingSpanTrackerTests(unittest.TestCase):
    def test_open_attempt_creates_root_and_canonical_stage_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = ProcessingSpanTracker(ProcessingSpanRepository(Path(tmp) / "rag.sqlite3"))

            root, attempt = tracker.open_attempt(
                knowledge_id="doc-1",
                input={"file_name": "manual.txt"},
                metadata={"trace_id": "trace-1"},
            )

            self.assertIsNotNone(root)
            self.assertEqual(1, attempt)
            tree = tracker.latest_tree("doc-1")
            self.assertIsNotNone(tree)
            self.assertEqual("knowledge_processing", tree["root"]["name"])
            self.assertEqual(
                ["docreader", "chunking", "embedding", "multimodal", "postprocess"],
                [stage["name"] for stage in tree["root"]["children"]],
            )

    def test_fail_stage_cancels_dependent_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = ProcessingSpanTracker(ProcessingSpanRepository(Path(tmp) / "rag.sqlite3"))
            _, attempt = tracker.open_attempt(knowledge_id="doc-1", input={}, metadata={})
            stage = tracker.begin_stage("doc-1", attempt, "chunking", {"strategy": "auto"})

            tracker.fail_span(stage, RuntimeError("chunk failed"))

            tree = tracker.latest_tree("doc-1")
            stages = {stage["name"]: stage for stage in tree["root"]["children"]}
            self.assertEqual(STATUS_FAILED, stages["chunking"]["status"])
            self.assertEqual(STATUS_CANCELLED, stages["embedding"]["status"])
            self.assertEqual(STATUS_CANCELLED, stages["multimodal"]["status"])
            self.assertEqual(STATUS_CANCELLED, stages["postprocess"]["status"])

    def test_end_stage_records_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = ProcessingSpanTracker(ProcessingSpanRepository(Path(tmp) / "rag.sqlite3"))
            root, attempt = tracker.open_attempt(knowledge_id="doc-1", input={}, metadata={})
            stage = tracker.begin_stage("doc-1", attempt, "docreader", {"file_name": "manual.txt"})

            tracker.end_span(stage, {"characters": 120})
            tracker.finalize_attempt(root, status=STATUS_DONE)

            tree = tracker.latest_tree("doc-1")
            stages = {stage["name"]: stage for stage in tree["root"]["children"]}
            self.assertEqual(STATUS_DONE, stages["docreader"]["status"])
            self.assertEqual({"characters": 120}, stages["docreader"]["output"])

    def test_subspan_and_generation_nodes_are_nested_and_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = ProcessingSpanTracker(ProcessingSpanRepository(Path(tmp) / "rag.sqlite3"))
            _, attempt = tracker.open_attempt(knowledge_id="doc-1", input={}, metadata={})
            stage = tracker.begin_stage("doc-1", attempt, "embedding", {"api_key": "secret-key"})

            batch = tracker.begin_subspan(stage, "embedding_batch", input={"texts": ["hello"]}, metadata={"token": "abc"})
            generation = tracker.begin_generation(batch, "openai_embeddings", input={"prompt": "x" * 2200})
            tracker.end_span(generation, {"vector_count": 1})
            tracker.end_span(batch, {"batch_size": 1})
            tracker.end_span(stage, {"chunks": 1})

            tree = tracker.latest_tree("doc-1")
            stages = {stage["name"]: stage for stage in tree["root"]["children"]}
            embedding = stages["embedding"]
            self.assertEqual("[redacted]", embedding["input"]["api_key"])
            self.assertEqual(SPAN_SUBSPAN, embedding["children"][0]["kind"])
            self.assertEqual("[redacted]", embedding["children"][0]["metadata"]["token"])
            self.assertEqual(SPAN_GENERATION, embedding["children"][0]["children"][0]["kind"])
            self.assertTrue(embedding["children"][0]["children"][0]["input"]["prompt"].endswith("...[truncated]"))

    def test_abort_attempt_cancels_open_spans(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = ProcessingSpanTracker(ProcessingSpanRepository(Path(tmp) / "rag.sqlite3"))
            root, attempt = tracker.open_attempt(knowledge_id="doc-1", input={}, metadata={})
            tracker.begin_stage("doc-1", attempt, "docreader", {})

            tracker.abort_attempt(root, reason="user canceled")

            tree = tracker.latest_tree("doc-1")
            self.assertEqual(STATUS_CANCELLED, tree["root"]["status"])
            self.assertTrue(all(stage["status"] == STATUS_CANCELLED for stage in tree["root"]["children"]))

    def test_cancel_descendants_only_closes_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = ProcessingSpanTracker(ProcessingSpanRepository(Path(tmp) / "rag.sqlite3"))
            _, attempt = tracker.open_attempt(knowledge_id="doc-1", input={}, metadata={})
            stage = tracker.begin_stage("doc-1", attempt, "chunking", {})
            child = tracker.begin_subspan(stage, "heading_attempt")
            tracker.begin_generation(child, "diagnostic_model")

            cancelled = tracker.cancel_descendants(stage, "fallback selected")

            self.assertEqual(2, cancelled)
            tree = tracker.latest_tree("doc-1")
            chunking = {stage["name"]: stage for stage in tree["root"]["children"]}["chunking"]
            self.assertEqual(STATUS_RUNNING, chunking["status"])
            self.assertEqual(STATUS_CANCELLED, chunking["children"][0]["status"])
            self.assertEqual(STATUS_CANCELLED, chunking["children"][0]["children"][0]["status"])

    def test_retry_reentry_refreshes_same_named_running_subspan(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = ProcessingSpanTracker(ProcessingSpanRepository(Path(tmp) / "rag.sqlite3"))
            _, attempt = tracker.open_attempt(knowledge_id="doc-1", input={}, metadata={})
            stage = tracker.begin_stage("doc-1", attempt, "chunking", {})
            first = tracker.begin_subspan(stage, "heuristic_attempt", input={"try": 1})

            second = tracker.begin_subspan(stage, "heuristic_attempt", input={"try": 2})

            self.assertEqual(first.span_id, second.span_id)
            row = tracker.lookup_span_by_name("doc-1", attempt, "heuristic_attempt", parent_span_id=stage.span_id, kind=SPAN_SUBSPAN)
            self.assertEqual(STATUS_RUNNING, row["status"])
            self.assertEqual({"try": 2}, row["input_json"])
            tree = tracker.latest_tree("doc-1")
            chunking = {stage["name"]: stage for stage in tree["root"]["children"]}["chunking"]
            self.assertEqual(1, len(chunking["children"]))

    def test_heartbeat_updates_active_span_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = ProcessingSpanTracker(ProcessingSpanRepository(Path(tmp) / "rag.sqlite3"))
            _, attempt = tracker.open_attempt(knowledge_id="doc-1", input={}, metadata={})
            stage = tracker.begin_stage("doc-1", attempt, "docreader", {})
            before = tracker.lookup_stage("doc-1", attempt, "docreader")["updated_at"]
            time.sleep(0.01)

            tracker.heartbeat(stage)

            after = tracker.lookup_stage("doc-1", attempt, "docreader")["updated_at"]
            self.assertGreater(after, before)


if __name__ == "__main__":
    unittest.main()
