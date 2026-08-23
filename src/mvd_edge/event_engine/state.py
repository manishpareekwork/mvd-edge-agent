from dataclasses import dataclass
from datetime import datetime
import time
from typing import Optional
from uuid import uuid4


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class DetectedEvent:
    edge_event_id: str
    event_type: str
    epc: str
    edge_event_at: str
    reader_id: Optional[str] = None


class PresenceState:
    def __init__(self, exit_timeout: float) -> None:
        self.exit_timeout = exit_timeout
        self.visible_tags: dict[str, float] = {}

    def update(
        self,
        visible_epcs: list[str],
        now: Optional[float] = None,
        reader_id: Optional[str] = None,
    ) -> list[DetectedEvent]:
        observed_at = now if now is not None else time.time()
        events: list[DetectedEvent] = []

        for epc in visible_epcs:
            tag_key = self._tag_key(epc=epc, reader_id=reader_id)

            if tag_key not in self.visible_tags:
                events.append(
                    DetectedEvent(
                        edge_event_id=str(uuid4()),
                        event_type="ENTER",
                        epc=epc,
                        edge_event_at=timestamp(),
                        reader_id=reader_id,
                    )
                )

            self.visible_tags[tag_key] = observed_at

        expired_keys: list[str] = []

        for tag_key, last_seen in self.visible_tags.items():
            if reader_id is not None and not tag_key.startswith(f"{reader_id}\x00"):
                continue

            if observed_at - last_seen >= self.exit_timeout:
                events.append(
                    DetectedEvent(
                        edge_event_id=str(uuid4()),
                        event_type="EXIT",
                        epc=self._epc_from_key(tag_key),
                        edge_event_at=timestamp(),
                        reader_id=reader_id,
                    )
                )
                expired_keys.append(tag_key)

        for tag_key in expired_keys:
            del self.visible_tags[tag_key]

        return events

    def _tag_key(self, *, epc: str, reader_id: Optional[str]) -> str:
        if reader_id is None:
            return epc

        return f"{reader_id}\x00{epc}"

    def _epc_from_key(self, tag_key: str) -> str:
        return tag_key.split("\x00", 1)[1] if "\x00" in tag_key else tag_key
