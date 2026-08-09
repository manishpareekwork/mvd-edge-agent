import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mvd_edge.app import build_event_payload, process_pending_deliveries
from mvd_edge.event_engine.state import PresenceState
from mvd_edge.health.state import HealthState
from mvd_edge.storage.queue import DELIVERED, PENDING, EventQueue
from mvd_edge.transport.cloud import DeliveryResult


class FakeTransport:
    def __init__(self, results):
        self.results = list(results)
        self.sent_payloads = []

    def send_payload(self, payload):
        self.sent_payloads.append(dict(payload))
        result = self.results.pop(0)

        if isinstance(result, Exception):
            raise result

        return result


class AppQueueDeliveryTests(unittest.TestCase):
    def test_cloud_failure_then_recovery_preserves_edge_event_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch("builtins.print"):
            state = PresenceState(exit_timeout=3.0)
            event = state.update(["EPC1"], now=100.0)[0]
            queue = EventQueue(Path(directory) / "events.sqlite3")
            health = HealthState()
            queue.enqueue(build_event_payload(event, reader_id="LAB-RFID-01"))

            failing_transport = FakeTransport([TimeoutError("timeout")])
            process_pending_deliveries(
                queue=queue,
                transport=failing_transport,
                batch_size=20,
                health_state=health,
            )

            failed_event = queue.get(event.edge_event_id)
            self.assertEqual(failed_event.status, PENDING)
            self.assertEqual(failed_event.attempt_count, 1)
            self.assertEqual(health.last_error, "CLOUD_DELIVERY_FAILED")

            healthy_transport = FakeTransport([
                DeliveryResult(success=True, status="stored", event_id="cloud-event-1")
            ])
            process_pending_deliveries(
                queue=queue,
                transport=healthy_transport,
                batch_size=20,
                health_state=health,
            )

            delivered_event = queue.get(event.edge_event_id)
            self.assertEqual(delivered_event.status, DELIVERED)
            self.assertEqual(delivered_event.attempt_count, 2)
            self.assertIsNotNone(health.last_cloud_delivery_at)
            self.assertEqual(
                healthy_transport.sent_payloads[0]["edge_event_id"],
                event.edge_event_id,
            )
            self.assertEqual(
                failing_transport.sent_payloads[0]["edge_event_id"],
                healthy_transport.sent_payloads[0]["edge_event_id"],
            )
            queue.close()

    def test_already_stored_result_marks_delivered(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch("builtins.print"):
            state = PresenceState(exit_timeout=3.0)
            event = state.update(["EPC1"], now=100.0)[0]
            queue = EventQueue(Path(directory) / "events.sqlite3")
            health = HealthState()
            queue.enqueue(build_event_payload(event, reader_id="LAB-RFID-01"))
            transport = FakeTransport([
                DeliveryResult(
                    success=True,
                    duplicate=True,
                    status="already_stored",
                    event_id="cloud-event-1",
                )
            ])

            process_pending_deliveries(
                queue=queue,
                transport=transport,
                batch_size=20,
                health_state=health,
            )

            self.assertEqual(queue.get(event.edge_event_id).status, DELIVERED)
            self.assertIsNotNone(health.last_cloud_delivery_at)
            queue.close()


if __name__ == "__main__":
    unittest.main()
