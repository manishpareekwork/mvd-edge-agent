import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mvd_edge.adapters.idt85 import ANSWER_MODE, SCAN_MODE
from mvd_edge.app import (
    ReaderState,
    build_event_payload,
    connect_and_verify_reader,
    process_pending_deliveries,
    read_inventory_events,
)
from mvd_edge.event_engine.state import PresenceState
from mvd_edge.storage.queue import DELIVERED, EventQueue
from mvd_edge.transport.cloud import DeliveryResult


class FakeReader:
    def __init__(
        self,
        *,
        opens=True,
        verifies=True,
        modes=None,
        inventory_results=None,
    ) -> None:
        self.port = "/dev/test-reader"
        self.baudrate = 57600
        self.opens = opens
        self.verifies = verifies
        self.modes = list(modes or [ANSWER_MODE])
        self.inventory_results = list(inventory_results or [])
        self.open_count = 0
        self.close_count = 0
        self.verify_count = 0
        self.set_answer_mode_count = 0

    def open(self) -> None:
        self.open_count += 1

        if self.opens is not True:
            raise self.opens

    def close(self) -> None:
        self.close_count += 1

    def verify_reader(self) -> bool:
        self.verify_count += 1
        return self.verifies

    def get_work_mode(self):
        if len(self.modes) > 1:
            return self.modes.pop(0)

        return self.modes[0]

    def set_answer_mode(self) -> bool:
        self.set_answer_mode_count += 1
        return True

    def apply_installation_profile(self, target_read_distance_m=None) -> None:
        self.target_read_distance_m = target_read_distance_m

    def inventory(self):
        result = self.inventory_results.pop(0)

        if isinstance(result, Exception):
            raise result

        return result


class FakeTransport:
    def __init__(self):
        self.sent_payloads = []

    def send_payload(self, payload):
        self.sent_payloads.append(dict(payload))
        return DeliveryResult(success=True, status="stored", event_id="cloud-event-1")


class ReaderRecoveryTests(unittest.TestCase):
    def test_valid_answer_mode_reader_opens_and_verifies(self) -> None:
        reader = FakeReader(modes=[ANSWER_MODE])

        with patch("builtins.print"):
            state, message = connect_and_verify_reader(
                reader=reader,
                auto_configure_reader=False,
            )

        self.assertEqual(state, ReaderState.READY)
        self.assertEqual(message, "Communication verified")
        self.assertEqual(reader.open_count, 1)
        self.assertEqual(reader.verify_count, 1)

    def test_startup_without_reader_enters_reconnect_state(self) -> None:
        reader = FakeReader(opens=OSError("port missing"))

        with patch("builtins.print"):
            state, message = connect_and_verify_reader(
                reader=reader,
                auto_configure_reader=False,
            )

        self.assertEqual(state, ReaderState.DISCONNECTED)
        self.assertIn("port missing", message)
        self.assertEqual(reader.close_count, 1)

    def test_invalid_reader_response_does_not_proceed_to_inventory(self) -> None:
        reader = FakeReader(verifies=False, inventory_results=[["EPC1"]])

        with patch("builtins.print"):
            state, _message = connect_and_verify_reader(
                reader=reader,
                auto_configure_reader=False,
            )

        self.assertEqual(state, ReaderState.CONFIG_ERROR)
        self.assertEqual(reader.close_count, 1)
        self.assertEqual(len(reader.inventory_results), 1)

    def test_scan_mode_without_auto_configure_does_not_inventory(self) -> None:
        reader = FakeReader(modes=[SCAN_MODE], inventory_results=[["EPC1"]])

        with patch("builtins.print"):
            state, message = connect_and_verify_reader(
                reader=reader,
                auto_configure_reader=False,
            )

        self.assertEqual(state, ReaderState.CONFIG_ERROR)
        self.assertIn("Required: ANSWER", message)
        self.assertEqual(reader.set_answer_mode_count, 0)
        self.assertEqual(len(reader.inventory_results), 1)

    def test_scan_mode_with_auto_configure_verifies_answer_then_ready(self) -> None:
        reader = FakeReader(modes=[SCAN_MODE, ANSWER_MODE])

        with patch("builtins.print"):
            state, message = connect_and_verify_reader(
                reader=reader,
                auto_configure_reader=True,
            )

        self.assertEqual(state, ReaderState.READY)
        self.assertEqual(message, "Communication verified")
        self.assertEqual(reader.set_answer_mode_count, 1)

    def test_disconnect_closes_reader_and_reconnect_resumes_inventory(self) -> None:
        state = PresenceState(exit_timeout=3.0)
        reader = FakeReader(inventory_results=[["EPC1"], OSError("lost serial")])

        first_state, first_events, _ = read_inventory_events(reader, state)
        second_state, second_events, message = read_inventory_events(reader, state)

        self.assertEqual(first_state, ReaderState.READY)
        self.assertEqual(len(first_events), 1)
        self.assertEqual(second_state, ReaderState.DISCONNECTED)
        self.assertEqual(second_events, [])
        self.assertIn("lost serial", message)
        self.assertEqual(reader.close_count, 1)

        reconnected_reader = FakeReader(modes=[ANSWER_MODE], inventory_results=[["EPC1"]])

        with patch("builtins.print"):
            reconnect_state, _ = connect_and_verify_reader(
                reader=reconnected_reader,
                auto_configure_reader=False,
            )

        inventory_state, events, _ = read_inventory_events(reconnected_reader, state)

        self.assertEqual(reconnect_state, ReaderState.READY)
        self.assertEqual(inventory_state, ReaderState.READY)
        self.assertEqual(events, [])

    def test_reader_outage_does_not_generate_false_exit(self) -> None:
        state = PresenceState(exit_timeout=3.0)
        state.update(["EPC1"], now=100.0)
        reader = FakeReader(inventory_results=[OSError("lost serial")])

        with patch("time.time", return_value=200.0):
            reader_state, events, _ = read_inventory_events(reader, state)

        self.assertEqual(reader_state, ReaderState.DISCONNECTED)
        self.assertEqual(events, [])
        self.assertIn("EPC1", state.visible_tags)

    def test_cloud_queue_delivery_runs_while_reader_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch("builtins.print"):
            queue = EventQueue(Path(directory) / "events.sqlite3")
            state = PresenceState(exit_timeout=3.0)
            event = state.update(["EPC1"], now=100.0)[0]
            queue.enqueue(build_event_payload(event, reader_id="LAB-RFID-01"))
            transport = FakeTransport()

            delivered = process_pending_deliveries(
                queue=queue,
                transport=transport,
                batch_size=20,
            )

            self.assertEqual(delivered, 1)
            self.assertEqual(queue.get(event.edge_event_id).status, DELIVERED)
            self.assertEqual(len(transport.sent_payloads), 1)
            queue.close()


if __name__ == "__main__":
    unittest.main()
