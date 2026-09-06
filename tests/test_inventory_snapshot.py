import unittest
from mvd_edge.health.state import HealthState


class InventorySnapshotTests(unittest.TestCase):
    def test_current_inventory_is_copied_and_empty_scan_clears_tags(self):
        health=HealthState()
        tags=['A','B']
        health.mark_inventory_success(tags)
        tags.append('C')
        self.assertEqual(health.last_inventory_epcs,['A','B'])
        health.mark_inventory_success([])
        self.assertEqual(health.last_inventory_epcs,[])

    def test_failed_inventory_does_not_refresh_observation_time(self):
        health=HealthState()
        health.mark_inventory_success(['A'])
        seen=health.last_successful_inventory_at
        health.mark_inventory_no_response()
        self.assertEqual(health.last_successful_inventory_at,seen)
        self.assertFalse(health.inventory_responding)
