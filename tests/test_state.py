import unittest
from uuid import UUID

from mvd_edge.event_engine.state import PresenceState


class PresenceStateTests(unittest.TestCase):
    def test_enter_is_emitted_for_new_tag(self) -> None:
        state = PresenceState(exit_timeout=3.0)

        events = state.update(["EPC1"], now=100.0)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "ENTER")
        self.assertEqual(events[0].epc, "EPC1")
        self.assertIsInstance(UUID(events[0].edge_event_id), UUID)

    def test_seen_tag_does_not_emit_repeated_enter(self) -> None:
        state = PresenceState(exit_timeout=3.0)

        state.update(["EPC1"], now=100.0)
        events = state.update(["EPC1"], now=101.0)

        self.assertEqual(events, [])

    def test_exit_is_emitted_after_timeout(self) -> None:
        state = PresenceState(exit_timeout=3.0)

        state.update(["EPC1"], now=100.0)
        events = state.update([], now=103.0)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "EXIT")
        self.assertEqual(events[0].epc, "EPC1")
        self.assertIsInstance(UUID(events[0].edge_event_id), UUID)
        self.assertNotIn("EPC1", state.visible_tags)

    def test_separate_logical_events_receive_different_ids(self) -> None:
        state = PresenceState(exit_timeout=3.0)

        first_events = state.update(["EPC1"], now=100.0)
        state.update([], now=103.0)
        second_events = state.update(["EPC1"], now=104.0)

        self.assertNotEqual(
            first_events[0].edge_event_id,
            second_events[0].edge_event_id,
        )


if __name__ == "__main__":
    unittest.main()
