import tempfile
import unittest
from pathlib import Path

from mvd_edge.storage.queue import DELIVERED, PENDING, EventQueue


def payload(edge_event_id: str, epc: str = "EPC1") -> dict[str, str]:
    return {
        "edge_event_id": edge_event_id,
        "event": "ENTER",
        "epc": epc,
        "reader_id": "LAB-RFID-01",
        "timestamp": "2026-08-10T10:00:00.000+05:30",
        "edge_event_at": "2026-08-10T10:00:00.000+05:30",
        "edge_send_at": "2026-08-10T10:00:01.000+05:30",
    }


class EventQueueTests(unittest.TestCase):
    def queue_path(self, directory: str) -> Path:
        return Path(directory) / "events.sqlite3"

    def test_enqueue_creates_row_and_reports_depth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            queue = EventQueue(self.queue_path(directory))
            queue.enqueue(payload("event-1"))

            self.assertEqual(queue.pending_count(), 1)
            self.assertEqual(queue.fetch_pending(limit=10)[0].edge_event_id, "event-1")
            queue.close()

    def test_duplicate_edge_event_id_does_not_create_second_row(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            queue = EventQueue(self.queue_path(directory))
            queue.enqueue(payload("event-1", epc="EPC1"))
            queue.enqueue(payload("event-1", epc="EPC2"))

            self.assertEqual(queue.pending_count(), 1)
            self.assertEqual(queue.fetch_pending(limit=10)[0].payload["epc"], "EPC1")
            queue.close()

    def test_pending_event_survives_queue_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = self.queue_path(directory)
            queue = EventQueue(db_path)
            queue.enqueue(payload("event-1"))
            queue.close()

            reopened = EventQueue(db_path)
            pending = reopened.fetch_pending(limit=10)

            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0].edge_event_id, "event-1")
            reopened.close()

    def test_fetch_pending_returns_oldest_first(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            queue = EventQueue(self.queue_path(directory))
            queue.enqueue(payload("event-1"))
            queue.enqueue(payload("event-2"))

            self.assertEqual(
                [event.edge_event_id for event in queue.fetch_pending(limit=10)],
                ["event-1", "event-2"],
            )
            queue.close()

    def test_failed_delivery_increments_attempt_and_remains_pending(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            queue = EventQueue(self.queue_path(directory))
            queue.enqueue(payload("event-1"))
            queue.mark_attempt("event-1", error="timeout")

            event = queue.get("event-1")

            self.assertEqual(event.attempt_count, 1)
            self.assertEqual(event.status, PENDING)
            self.assertEqual(event.last_error, "timeout")
            queue.close()

    def test_successful_delivery_becomes_delivered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            queue = EventQueue(self.queue_path(directory))
            queue.enqueue(payload("event-1"))
            queue.mark_attempt("event-1")
            queue.mark_delivered("event-1")

            event = queue.get("event-1")

            self.assertEqual(event.status, DELIVERED)
            self.assertIsNotNone(event.delivered_at)
            self.assertIsNone(event.last_error)
            self.assertEqual(queue.pending_count(), 0)
            queue.close()

    def test_already_stored_response_can_be_marked_delivered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            queue = EventQueue(self.queue_path(directory))
            queue.enqueue(payload("event-1"))
            queue.mark_attempt("event-1")
            queue.mark_delivered("event-1")

            self.assertEqual(queue.get("event-1").status, DELIVERED)
            queue.close()

    def test_payload_json_round_trips_edge_event_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            queue = EventQueue(self.queue_path(directory))
            queue.enqueue(payload("event-1"))

            queued = queue.fetch_pending(limit=10)[0]

            self.assertEqual(queued.payload["edge_event_id"], "event-1")
            queue.close()

    def test_restart_persists_delivered_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = self.queue_path(directory)
            queue = EventQueue(db_path)
            queue.enqueue(payload("event-1"))
            queue.close()

            reopened = EventQueue(db_path)
            self.assertEqual(len(reopened.fetch_pending(limit=10)), 1)
            reopened.mark_attempt("event-1")
            reopened.mark_delivered("event-1")
            reopened.close()

            final = EventQueue(db_path)

            self.assertEqual(final.get("event-1").status, DELIVERED)
            self.assertEqual(final.pending_count(), 0)
            final.close()


if __name__ == "__main__":
    unittest.main()
