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

    def test_continuous_reads_exit_then_enter_again(self) -> None:
        state = PresenceState(exit_timeout=3.0)

        self.assertEqual(state.update(["EPC1"], now=100.0)[0].event_type, "ENTER")
        self.assertEqual(state.update(["EPC1"], now=101.0), [])
        self.assertEqual(state.update(["EPC1"], now=102.0), [])

        exit_events = state.update([], now=105.0)

        self.assertEqual(len(exit_events), 1)
        self.assertEqual(exit_events[0].event_type, "EXIT")
        self.assertNotIn("EPC1", state.visible_tags)

        reenter_events = state.update(["EPC1"], now=105.1)

        self.assertEqual(len(reenter_events), 1)
        self.assertEqual(reenter_events[0].event_type, "ENTER")

    def test_short_disappearance_does_not_exit(self) -> None:
        state = PresenceState(exit_timeout=3.0)

        state.update(["EPC1"], now=100.0)
        self.assertEqual(state.update([], now=102.9), [])
        self.assertIn("EPC1", state.visible_tags)

    def test_twenty_complete_cycles_for_same_epc(self) -> None:
        state = PresenceState(exit_timeout=3.0)

        for cycle in range(20):
            base = cycle * 10.0

            enter_events = state.update(["EPC1"], now=base)
            exit_events = state.update([], now=base + 3.0)

            self.assertEqual(len(enter_events), 1)
            self.assertEqual(enter_events[0].event_type, "ENTER")
            self.assertEqual(len(exit_events), 1)
            self.assertEqual(exit_events[0].event_type, "EXIT")
            self.assertNotIn("EPC1", state.visible_tags)

    def test_two_epcs_timeout_independently(self) -> None:
        state = PresenceState(exit_timeout=3.0)

        state.update(["EPC1", "EPC2"], now=100.0)
        state.update(["EPC1"], now=101.0)
        events = state.update(["EPC1"], now=103.0)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "EXIT")
        self.assertEqual(events[0].epc, "EPC2")
        self.assertIn("EPC1", state.visible_tags)
        self.assertNotIn("EPC2", state.visible_tags)


if __name__ == "__main__":
    unittest.main()
