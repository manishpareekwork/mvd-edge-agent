from dataclasses import dataclass
from datetime import datetime
import time
from typing import Optional


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class DetectedEvent:
    event_type: str
    epc: str
    edge_event_at: str


class PresenceState:
    def __init__(self, exit_timeout: float) -> None:
        self.exit_timeout = exit_timeout
        self.visible_tags: dict[str, float] = {}

    def update(
        self,
        visible_epcs: list[str],
        now: Optional[float] = None,
    ) -> list[DetectedEvent]:
        observed_at = now if now is not None else time.time()
        events: list[DetectedEvent] = []

        for epc in visible_epcs:
            if epc not in self.visible_tags:
                events.append(
                    DetectedEvent(
                        event_type="ENTER",
                        epc=epc,
                        edge_event_at=timestamp(),
                    )
                )

            self.visible_tags[epc] = observed_at

        expired_epcs: list[str] = []

        for epc, last_seen in self.visible_tags.items():
            if observed_at - last_seen >= self.exit_timeout:
                events.append(
                    DetectedEvent(
                        event_type="EXIT",
                        epc=epc,
                        edge_event_at=timestamp(),
                    )
                )
                expired_epcs.append(epc)

        for epc in expired_epcs:
            del self.visible_tags[epc]

        return events
