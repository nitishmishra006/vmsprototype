"""The Monitoring DSL (SPEC §8).

A natural-language instruction compiles into ``MonitoringPlanDSL``. Every model
output and every API payload is validated here (CLAUDE.md hard rule #6), including
per-condition-type parameter checks so an invalid plan can never reach the event
engine.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EntityKind(str, Enum):
    detector_class = "detector_class"
    open_vocab = "open_vocab"
    concept = "concept"
    anchor = "anchor"
    zone = "zone"


class PlanMode(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    SEMANTIC_MONITORING = "SEMANTIC_MONITORING"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ConditionType(str, Enum):
    present = "present"
    in_zone = "in_zone"
    outside_zone = "outside_zone"
    enters_zone = "enters_zone"
    exits_zone = "exits_zone"
    near = "near"
    far = "far"
    overlaps = "overlaps"
    approaching = "approaching"
    moving_away = "moving_away"
    moving = "moving"
    stopped = "stopped"
    speed_above = "speed_above"
    count_in_zone_above = "count_in_zone_above"
    absent_from_zone = "absent_from_zone"
    semantic = "semantic"


#: Condition types that require a second entity (``object``).
BINARY_CONDITIONS: frozenset[ConditionType] = frozenset(
    {
        ConditionType.near,
        ConditionType.far,
        ConditionType.overlaps,
        ConditionType.approaching,
        ConditionType.moving_away,
    }
)

#: Condition types that operate on a zone (``params.zone``).
ZONE_CONDITIONS: frozenset[ConditionType] = frozenset(
    {
        ConditionType.in_zone,
        ConditionType.outside_zone,
        ConditionType.enters_zone,
        ConditionType.exits_zone,
        ConditionType.count_in_zone_above,
        ConditionType.absent_from_zone,
    }
)

VALID_UNITS = ("m", "px")
SPEED_UNITS = ("m/s", "px/s")


def _require_number(value: Any, ctype: ConditionType, key: str) -> float:
    """Return ``value`` as a float, or raise with a message naming the condition.

    ``bool`` is rejected explicitly: it is a subclass of ``int`` in Python, and
    ``{"max_distance": true}`` must not silently become a distance of 1.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):  # noqa: UP038
        raise ValueError(f"condition '{ctype.value}' requires numeric params.{key}")
    return float(value)


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str = Field(min_length=1)
    kind: EntityKind
    ref: str = Field(min_length=1)


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ConditionType
    subject: str = Field(min_length=1)
    object: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_shape(self) -> Condition:
        ctype = self.type
        params = self.params

        if ctype in BINARY_CONDITIONS and not self.object:
            raise ValueError(f"condition '{ctype.value}' requires an 'object' entity")
        if (
            ctype not in BINARY_CONDITIONS
            and ctype is not ConditionType.semantic
            and self.object is not None
        ):
            raise ValueError(f"condition '{ctype.value}' does not take an 'object'")

        if ctype in ZONE_CONDITIONS:
            zone = params.get("zone")
            if not isinstance(zone, str) or not zone:
                raise ValueError(f"condition '{ctype.value}' requires params.zone (string)")

        if ctype in (ConditionType.near, ConditionType.far):
            key = "max_distance" if ctype is ConditionType.near else "min_distance"
            value = _require_number(params.get(key), ctype, key)
            if value <= 0:
                raise ValueError(f"params.{key} must be > 0")
            if params.get("units") not in VALID_UNITS:
                raise ValueError(
                    f"condition '{ctype.value}' requires params.units in {VALID_UNITS}"
                )

        if ctype in (ConditionType.moving, ConditionType.speed_above):
            value = _require_number(params.get("min_speed"), ctype, "min_speed")
            if value < 0:
                raise ValueError("params.min_speed must be >= 0")
            if params.get("units") not in SPEED_UNITS:
                raise ValueError(
                    f"condition '{ctype.value}' requires params.units in {SPEED_UNITS}"
                )

        if (
            ctype is ConditionType.stopped
            and params.get("max_speed") is not None
            and _require_number(params.get("max_speed"), ctype, "max_speed") < 0
        ):
            raise ValueError("params.max_speed must be a number >= 0")

        if ctype is ConditionType.count_in_zone_above:
            value = params.get("count")
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(
                    "condition 'count_in_zone_above' requires integer params.count >= 1"
                )

        if ctype is ConditionType.semantic:
            action = params.get("action")
            if not isinstance(action, str) or not action:
                raise ValueError("condition 'semantic' requires params.action (string)")
            trigger = params.get("trigger")
            if trigger is not None and trigger not in {c.value for c in ConditionType}:
                raise ValueError("params.trigger must be a known condition type")

        if ctype is ConditionType.present:
            zone = params.get("zone")
            if zone is not None and (not isinstance(zone, str) or not zone):
                raise ValueError("params.zone must be a non-empty string when given")

        return self


class MonitoringPlanDSL(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str = Field(min_length=1)
    source_text: str | None = None
    camera_ids: list[str] = Field(default_factory=list)
    mode: PlanMode = PlanMode.DETERMINISTIC
    entities: list[Entity] = Field(default_factory=list)
    conditions: list[Condition] = Field(default_factory=list)
    logic: Literal["all"] = "all"  # v1 is AND-only; OR = two plans (SPEC §8)
    duration_s: float = Field(default=0.0, ge=0.0)
    event_type: str = Field(min_length=1)
    severity: Severity = Severity.medium
    vlm_question: str | None = None
    enabled: bool = False

    @field_validator("entities")
    @classmethod
    def _unique_aliases(cls, v: list[Entity]) -> list[Entity]:
        aliases = [e.alias for e in v]
        dupes = {a for a in aliases if aliases.count(a) > 1}
        if dupes:
            raise ValueError(f"duplicate entity aliases: {sorted(dupes)}")
        return v

    @model_validator(mode="after")
    def _aliases_resolve(self) -> MonitoringPlanDSL:
        known = {e.alias for e in self.entities}
        for cond in self.conditions:
            if cond.subject not in known:
                raise ValueError(
                    f"condition subject '{cond.subject}' is not a declared entity alias"
                )
            if cond.object is not None and cond.object not in known:
                raise ValueError(f"condition object '{cond.object}' is not a declared entity alias")
        if self.mode is PlanMode.DETERMINISTIC and not self.conditions:
            raise ValueError("a DETERMINISTIC plan needs at least one condition")
        return self
