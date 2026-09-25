#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Typed body-need context shared by existing CCA8 owners, not a cognitive part.

Body sensory alone publishes this current representation. Feeding association and
operation circuitry consume its legitimate value and time; no record chooses a
source, task, completion, reward or motor permission. Physical intake pools and
observer-only supply totals are intentionally absent. The fixed constants are
engineering-profile parameters, not biological units or learning rules.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from cca8_motor_contracts import MotorStreamRefV1

__version__ = "0.1.0"
__all__ = ["FeedingNeedStateV1", "FEEDING_ADEQUACY_LIMIT_V1", "FEEDING_EVIDENCE_AGE_V1", "__version__"]
FEEDING_ADEQUACY_LIMIT_V1 = 0.01
FEEDING_EVIDENCE_AGE_V1 = 8


@dataclass(frozen=True, slots=True)
class FeedingNeedStateV1:
    """One immutable body-sensory reading at a declared focal evidence boundary.

    None-valued measurements and absent acquisitions remain distinguishable.
    new_acquisition is the sensory owner's replay-sensitive declaration; it does
    not mean task progress. Currentness allows a bounded age but never retimes a
    reading. Task circuitry, not this record, owns adequacy and confirmation.
    """

    stream: MotorStreamRefV1
    cycle_id: int
    cutoff_tick: int
    sample_id: int | None
    event_tick: int | None
    available_tick: int | None
    deficit_units: float | None
    new_acquisition: bool

    def __post_init__(self) -> None:
        if not isinstance(self.stream, MotorStreamRefV1) or not isinstance(self.new_acquisition, bool):
            raise TypeError("feeding-need context requires a stream and Boolean acquisition status")
        for focal_value, minimum in ((self.cycle_id, 1), (self.cutoff_tick, 0)):
            if isinstance(focal_value, bool) or not isinstance(focal_value, int) or not minimum <= focal_value < 2**63 - 97:
                raise ValueError("feeding-need focal identity/time is invalid")
        absent = self.sample_id is None
        if absent:
            if self.event_tick is not None or self.available_tick is not None or self.deficit_units is not None or self.new_acquisition:
                raise ValueError("absent feeding acquisition cannot supply data or new-sample status")
        else:
            for sample_value, minimum in ((self.sample_id, 1), (self.event_tick, 0), (self.available_tick, 0)):
                if isinstance(sample_value, bool) or not isinstance(sample_value, int) or not minimum <= sample_value < 2**63 - 97:
                    raise ValueError("feeding-need acquisition identity/time is invalid")
            if self.event_tick is None or self.available_tick is None or not self.event_tick <= self.available_tick <= self.cutoff_tick:
                raise ValueError("feeding-need evidence cannot be future")
        if self.deficit_units is not None:
            value = self.deficit_units
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 8:
                raise ValueError("feeding deficit must be an available finite synthetic measurement")

    @property
    def current(self) -> bool:
        """Report bounded evidential age, not freshness from rereading or task adequacy."""
        return (self.deficit_units is not None and self.event_tick is not None
                and self.cutoff_tick - self.event_tick <= FEEDING_EVIDENCE_AGE_V1)

    def as_dict(self) -> dict[str, object]:
        """Detach only legitimate body evidence; neither fed nor Rest is a field."""
        return {"owner": "body_sensory", "stream": self.stream.as_dict(), "cycle_id": self.cycle_id,
                "cutoff_tick": self.cutoff_tick, "sample_id": self.sample_id, "event_tick": self.event_tick,
                "available_tick": self.available_tick, "deficit_units": self.deficit_units,
                "new_acquisition": self.new_acquisition, "current": self.current, "units": "synthetic_feeding_deficit"}
