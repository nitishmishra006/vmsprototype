"""Monitoring DSL validation (SPEC §8) — valid and invalid plans."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.dsl import Condition, MonitoringPlanDSL

FORKLIFT_PLAN = {
    "id": "plan_123",
    "name": "Worker near moving forklift",
    "source_text": "Alert me if a worker gets within 2 m of a moving forklift",
    "camera_ids": ["CAM_01"],
    "mode": "DETERMINISTIC",
    "entities": [
        {"alias": "worker", "kind": "detector_class", "ref": "person"},
        {"alias": "forklift", "kind": "detector_class", "ref": "forklift"},
    ],
    "conditions": [
        {
            "type": "near",
            "subject": "worker",
            "object": "forklift",
            "params": {"max_distance": 2.0, "units": "m"},
        },
        {
            "type": "moving",
            "subject": "forklift",
            "params": {"min_speed": 0.3, "units": "m/s"},
        },
    ],
    "logic": "all",
    "duration_s": 2.0,
    "event_type": "unsafe_proximity",
    "severity": "high",
    "vlm_question": "Is a worker dangerously close to a moving forklift?",
    "enabled": True,
}


def test_spec_example_plan_validates() -> None:
    plan = MonitoringPlanDSL.model_validate(FORKLIFT_PLAN)
    assert plan.name == "Worker near moving forklift"
    assert plan.duration_s == 2.0
    assert len(plan.conditions) == 2


def test_absent_from_zone_plan_validates() -> None:
    plan = MonitoringPlanDSL.model_validate(
        {
            "name": "Nobody at desk",
            "entities": [{"alias": "me", "kind": "detector_class", "ref": "person"}],
            "conditions": [
                {"type": "absent_from_zone", "subject": "me", "params": {"zone": "desk"}}
            ],
            "duration_s": 10.0,
            "event_type": "desk_empty",
        }
    )
    assert plan.conditions[0].params["zone"] == "desk"


def test_semantic_monitoring_plan_needs_no_conditions() -> None:
    plan = MonitoringPlanDSL.model_validate(
        {
            "name": "Anything unusual near the furnace",
            "mode": "SEMANTIC_MONITORING",
            "entities": [{"alias": "furnace", "kind": "anchor", "ref": "furnace"}],
            "conditions": [],
            "event_type": "unusual_activity",
        }
    )
    assert plan.mode.value == "SEMANTIC_MONITORING"


def test_deterministic_plan_requires_a_condition() -> None:
    with pytest.raises(ValidationError, match="at least one condition"):
        MonitoringPlanDSL.model_validate(
            {
                "name": "Empty",
                "entities": [{"alias": "p", "kind": "detector_class", "ref": "person"}],
                "conditions": [],
                "event_type": "nothing",
            }
        )


def test_condition_subject_must_be_a_declared_alias() -> None:
    with pytest.raises(ValidationError, match="not a declared entity alias"):
        MonitoringPlanDSL.model_validate(
            {
                "name": "Dangling subject",
                "entities": [{"alias": "worker", "kind": "detector_class", "ref": "person"}],
                "conditions": [{"type": "present", "subject": "ghost"}],
                "event_type": "x",
            }
        )


def test_duplicate_aliases_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate entity aliases"):
        MonitoringPlanDSL.model_validate(
            {
                "name": "Dupes",
                "entities": [
                    {"alias": "p", "kind": "detector_class", "ref": "person"},
                    {"alias": "p", "kind": "detector_class", "ref": "car"},
                ],
                "conditions": [{"type": "present", "subject": "p"}],
                "event_type": "x",
            }
        )


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        MonitoringPlanDSL.model_validate({**FORKLIFT_PLAN, "sneaky": True})


def test_or_logic_not_supported_in_v1() -> None:
    with pytest.raises(ValidationError):
        MonitoringPlanDSL.model_validate({**FORKLIFT_PLAN, "logic": "any"})


# --- per-condition parameter validation ----------------------------------
def test_near_requires_distance_and_units() -> None:
    with pytest.raises(ValidationError, match="max_distance"):
        Condition.model_validate(
            {"type": "near", "subject": "a", "object": "b", "params": {"units": "m"}}
        )
    with pytest.raises(ValidationError, match="units"):
        Condition.model_validate(
            {"type": "near", "subject": "a", "object": "b", "params": {"max_distance": 2.0}}
        )
    with pytest.raises(ValidationError, match="units"):
        Condition.model_validate(
            {
                "type": "near",
                "subject": "a",
                "object": "b",
                "params": {"max_distance": 2.0, "units": "furlongs"},
            }
        )


def test_near_requires_an_object_entity() -> None:
    with pytest.raises(ValidationError, match="requires an 'object'"):
        Condition.model_validate(
            {"type": "near", "subject": "a", "params": {"max_distance": 2.0, "units": "m"}}
        )


def test_zone_conditions_require_a_zone() -> None:
    for ctype in ("in_zone", "outside_zone", "enters_zone", "exits_zone", "absent_from_zone"):
        with pytest.raises(ValidationError, match="params.zone"):
            Condition.model_validate({"type": ctype, "subject": "a", "params": {}})


def test_count_in_zone_above_requires_positive_int() -> None:
    ok = Condition.model_validate(
        {"type": "count_in_zone_above", "subject": "p", "params": {"zone": "desk", "count": 1}}
    )
    assert ok.params["count"] == 1
    with pytest.raises(ValidationError, match="params.count"):
        Condition.model_validate(
            {"type": "count_in_zone_above", "subject": "p", "params": {"zone": "desk", "count": 0}}
        )
    with pytest.raises(ValidationError, match="params.count"):
        Condition.model_validate(
            {
                "type": "count_in_zone_above",
                "subject": "p",
                "params": {"zone": "desk", "count": 1.5},
            }
        )


def test_moving_requires_speed_units() -> None:
    with pytest.raises(ValidationError, match="units"):
        Condition.model_validate(
            {"type": "moving", "subject": "f", "params": {"min_speed": 0.3, "units": "m"}}
        )


def test_semantic_requires_action() -> None:
    with pytest.raises(ValidationError, match="params.action"):
        Condition.model_validate(
            {"type": "semantic", "subject": "w", "object": "t", "params": {"trigger": "overlaps"}}
        )
    ok = Condition.model_validate(
        {
            "type": "semantic",
            "subject": "w",
            "object": "t",
            "params": {"action": "climbing", "trigger": "overlaps"},
        }
    )
    assert ok.params["action"] == "climbing"


def test_semantic_trigger_must_be_known_condition() -> None:
    with pytest.raises(ValidationError, match="params.trigger"):
        Condition.model_validate(
            {
                "type": "semantic",
                "subject": "w",
                "object": "t",
                "params": {"action": "climbing", "trigger": "levitates"},
            }
        )


def test_unary_condition_rejects_object() -> None:
    with pytest.raises(ValidationError, match="does not take an 'object'"):
        Condition.model_validate({"type": "present", "subject": "a", "object": "b"})


def test_unknown_condition_type_rejected() -> None:
    with pytest.raises(ValidationError):
        Condition.model_validate({"type": "teleports", "subject": "a"})
