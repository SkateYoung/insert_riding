import unittest

from test import fleet_push_test_server as server


def _snapshot(vehicle_id, payload):
    return {
        "received_at": "2026-11-05 12:00:00",
        "path_vehicle_id": vehicle_id,
        "payload": payload,
    }


def _assignment(request_id, push_event_id, route_version="route-v1"):
    return {
        "event_type": "fleet_route_changed",
        "event_reason": "order_assigned",
        "request_id": request_id,
        "confirmation_request_id": request_id,
        "driver_push_confirmation_required": True,
        "route_version": route_version,
        "driver_push_route_version": route_version,
        "push_event_id": push_event_id,
        "push_revision": 1,
    }


def _correction(request_id, route_version="route-corrected"):
    return {
        "event_type": "fleet_route_corrected",
        "event_kind": "correction",
        "event_reason": "order_requeued_after_push_failure",
        "failed_request_id": request_id,
        "route_version": route_version,
    }


class FleetPushTestServerPendingNavigationTest(unittest.TestCase):
    def setUp(self):
        with server._lock:
            server._snapshots.clear()
            server._confirmations.clear()

    def tearDown(self):
        with server._lock:
            server._snapshots.clear()
            server._confirmations.clear()

    def _append(self, vehicle_id, payload):
        with server._lock:
            server._snapshots.append(_snapshot(vehicle_id, payload))

    def test_correction_hides_old_pending_confirmation(self):
        self._append("vehicle-a", _assignment("order-1", "push-old"))
        self._append("vehicle-a", _correction("order-1"))

        entries, _ = server._pending_navigation_entries("vehicle-a")

        self.assertEqual(entries, [])

    def test_reassignment_after_correction_is_visible(self):
        self._append("vehicle-a", _assignment("order-1", "push-old"))
        self._append("vehicle-a", _correction("order-1"))
        self._append(
            "vehicle-a",
            _assignment("order-1", "push-new", route_version="route-v2"),
        )

        entries, _ = server._pending_navigation_entries("vehicle-a")

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["push_event_id"], "push-new")
        self.assertEqual(entries[0]["route_version"], "route-v2")

    def test_old_confirmation_does_not_hide_new_assignment_event(self):
        self._append("vehicle-a", _assignment("order-1", "push-old"))
        old_key = server._confirmation_key("vehicle-a", "order-1", "push-old")
        with server._lock:
            server._confirmations[old_key] = {"status": "confirmed"}
        self._append(
            "vehicle-a",
            _assignment("order-1", "push-new", route_version="route-v2"),
        )

        entries, _ = server._pending_navigation_entries("vehicle-a")

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["push_event_id"], "push-new")

    def test_correction_only_invalidates_the_original_vehicle(self):
        self._append("vehicle-a", _assignment("order-1", "push-a"))
        self._append("vehicle-a", _correction("order-1"))
        self._append("vehicle-b", _assignment("order-1", "push-b"))

        old_entries, _ = server._pending_navigation_entries("vehicle-a")
        new_entries, _ = server._pending_navigation_entries("vehicle-b")

        self.assertEqual(old_entries, [])
        self.assertEqual(len(new_entries), 1)
        self.assertEqual(new_entries[0]["push_event_id"], "push-b")


if __name__ == "__main__":
    unittest.main()
