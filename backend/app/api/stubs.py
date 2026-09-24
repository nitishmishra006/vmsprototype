"""Not-yet-implemented endpoints from SPEC §20.

Each returns HTTP 501 naming the phase that implements it, so the API surface is
visible in /docs from day one and nothing ever returns a fake success
(CLAUDE.md hard rule #1). Routes are replaced by real implementations as phases land.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

router = APIRouter()

#: (methods, path, phase, description)
PLANNED_ENDPOINTS: tuple[tuple[tuple[str, ...], str, int, str], ...] = (
    (("GET",), "/webcams", 1, "probe local webcams with thumbnails"),
    (("GET", "POST"), "/cameras", 1, "list / create cameras"),
    (("DELETE",), "/cameras/{camera_id}", 1, "delete a camera"),
    (("GET",), "/cameras/{camera_id}/stream", 1, "MJPEG annotated stream"),
    (("GET",), "/cameras/{camera_id}/snapshot", 1, "single annotated snapshot"),
    (("GET",), "/world/{camera_id}", 1, "world model snapshot"),
    (("GET", "POST"), "/cameras/{camera_id}/zones", 2, "list / create zones"),
    (("DELETE",), "/zones/{zone_id}", 2, "delete a zone"),
    (("GET", "POST"), "/monitoring-plans", 2, "list / create monitoring plans"),
    (("PATCH", "DELETE"), "/monitoring-plans/{plan_id}", 2, "update / delete a plan"),
    (("GET",), "/events", 2, "list events"),
    (("GET",), "/events/{event_id}", 2, "event detail with evidence"),
    (("POST",), "/events/{event_id}/feedback", 2, "submit human feedback"),
    (("POST",), "/cameras/{camera_id}/missed-event", 2, "report a missed event"),
    (("POST",), "/cameras/{camera_id}/calibration", 3, "4-point floor calibration"),
    (("POST",), "/monitoring-plans/parse", 4, "natural-language plan parsing"),
    (("POST",), "/cameras/{camera_id}/anchors/propose", 5, "propose anchors by text"),
    (("GET", "POST"), "/anchors", 5, "list / save anchors"),
    (("GET", "POST"), "/concepts", 6, "list / create visual concepts"),
    (("PATCH", "DELETE"), "/concepts/{concept_id}", 6, "update / delete a concept"),
    (("POST",), "/concepts/{concept_id}/images", 6, "add concept reference images"),
    (("POST",), "/concepts/{concept_id}/test", 6, "test a concept against a camera"),
    (("GET",), "/learning-queue", 8, "learning queue items"),
    (("GET",), "/unknown-candidates", 8, "unknown object candidates"),
    (("GET",), "/monitoring-plans/{plan_id}/versions", 8, "plan version history"),
    (("GET",), "/improvements/suggestions", 8, "improvement suggestions"),
    (("POST",), "/improvements/suggestions/{suggestion_id}/replay", 8, "replay a suggestion"),
    (("POST",), "/improvements/suggestions/{suggestion_id}/apply", 8, "apply a suggestion"),
    (("POST",), "/improvements/suggestions/{suggestion_id}/dismiss", 8, "dismiss a suggestion"),
    (("GET",), "/improvements/history", 8, "applied improvement history"),
    (("POST",), "/improvements/history/{applied_id}/rollback", 8, "roll back an improvement"),
    (("GET",), "/improvements/trend", 8, "precision / false-alarm trend"),
)


def _slug(method: str, path: str) -> str:
    cleaned = path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
    return f"not_implemented_{method.lower()}_{cleaned}"


def _make_handler(method: str, path: str, phase: int, description: str):
    async def handler() -> None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                f"{method} '{path}' ({description}) is not implemented yet — it lands in "
                f"Phase {phase}. This is a scaffold stub, not a failure."
            ),
        )

    handler.__name__ = _slug(method, path)
    return handler


def register_stubs() -> None:
    """Register one route per (method, path) so each gets a unique operation id."""
    for methods, path, phase, description in PLANNED_ENDPOINTS:
        for method in methods:
            router.add_api_route(
                path,
                _make_handler(method, path, phase, description),
                methods=[method],
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                tags=[f"phase {phase} (not implemented)"],
                summary=f"{description} — Phase {phase}",
                operation_id=_slug(method, path),
            )


register_stubs()
