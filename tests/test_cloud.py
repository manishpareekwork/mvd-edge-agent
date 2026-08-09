import unittest
from unittest.mock import Mock, patch

from mvd_edge.transport.cloud import CloudTransport


class CloudTransportTests(unittest.TestCase):
    def payload(self) -> dict[str, str]:
        return {
            "edge_event_id": "c05f1668-19fd-46cf-9729-8d3e724385e2",
            "event": "ENTER",
            "epc": "EPC1",
            "reader_id": "LAB-RFID-01",
            "timestamp": "2026-08-10T10:00:00.000+05:30",
            "edge_event_at": "2026-08-10T10:00:00.000+05:30",
            "edge_send_at": "2026-08-10T10:00:01.000+05:30",
        }

    def test_transport_uses_supplied_edge_event_id(self) -> None:
        response = Mock()
        response.status_code = 201
        response.json.return_value = {
            "status": "stored",
            "duplicate": False,
            "event_id": "stored-event-id",
            "asset": None,
            "timing": {},
        }

        transport = CloudTransport(api_url="https://example.test/events")

        with patch("builtins.print"), patch(
            "mvd_edge.transport.cloud.requests.post",
            return_value=response,
        ) as post:
            result = transport.send_payload(self.payload())

        payload = post.call_args.kwargs["json"]

        self.assertEqual(
            payload["edge_event_id"],
            "c05f1668-19fd-46cf-9729-8d3e724385e2",
        )
        self.assertTrue(result.success)

    def test_repeated_send_preserves_same_edge_event_id(self) -> None:
        response = Mock()
        response.status_code = 201
        response.json.return_value = {
            "status": "already_stored",
            "duplicate": True,
            "event_id": "stored-event-id",
            "asset": None,
            "timing": {},
        }

        transport = CloudTransport(api_url="https://example.test/events")
        edge_event_id = "c05f1668-19fd-46cf-9729-8d3e724385e2"

        with patch("builtins.print"), patch(
            "mvd_edge.transport.cloud.requests.post",
            return_value=response,
        ) as post:
            for _ in range(2):
                payload = self.payload()
                payload["edge_event_id"] = edge_event_id
                result = transport.send_payload(payload)
                self.assertTrue(result.success)
                self.assertTrue(result.duplicate)

        payloads = [
            call.kwargs["json"]
            for call in post.call_args_list
        ]

        self.assertEqual(payloads[0]["edge_event_id"], edge_event_id)
        self.assertEqual(payloads[1]["edge_event_id"], edge_event_id)


if __name__ == "__main__":
    unittest.main()
