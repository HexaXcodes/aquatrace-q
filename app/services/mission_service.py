"""
Mission planning service (Phase 16).

Builds a ranked, ordered visit list for a survey's targets: filters out
`IGNORE`-priority targets and anything without coordinates, sorts the
rest by priority action then score, and orders stops with a simple
greedy nearest-neighbor walk (starting from the supplied vehicle
position) using real geodesic distances.

This is explicitly decision support -- it does NOT drive, command, or
navigate a real AUV/ROV (spec section 27/49). Route quality is
"reasonable", not provably optimal (true optimal routing is a
travelling-salesman problem; greedy nearest-neighbor is the right
complexity/quality tradeoff for a handful of targets in a hackathon
timeframe, and can be swapped for a proper solver later without
changing the API or database shape).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import MissionNotFoundError
from app.gis.geo_utils import geodesic_distance_m
from app.models.enums import MissionStatus, PriorityAction
from app.models.mission import Mission, MissionTarget
from app.models.priority import PriorityScore
from app.models.target import Target

_ACTION_RANK = {
    PriorityAction.VERIFY_NOW: 0,
    PriorityAction.VERIFY_NEXT: 1,
    PriorityAction.VERIFY_LATER: 2,
}


@dataclass(slots=True)
class _Candidate:
    target: Target
    priority: PriorityScore


def build_mission(
    db: Session,
    survey_id: str,
    start_latitude: float,
    start_longitude: float,
    vehicle_speed_mps: float | None = None,
    settings: Settings | None = None,
) -> Mission:
    settings = settings or get_settings()
    speed = vehicle_speed_mps or settings.MISSION_DEFAULT_VEHICLE_SPEED_MPS

    candidates = _rankable_candidates(db, survey_id)

    mission = Mission(
        survey_id=survey_id,
        status=MissionStatus.DRAFT,
        start_latitude=start_latitude,
        start_longitude=start_longitude,
        vehicle_speed_mps=speed,
    )
    db.add(mission)
    db.flush()  # assign mission.id without committing yet

    ordered = _sort_by_priority_then_nearest(candidates, start_latitude, start_longitude)

    cur_lat, cur_lon = start_latitude, start_longitude
    cumulative = 0.0
    for sequence, candidate in enumerate(ordered, start=1):
        distance = geodesic_distance_m(cur_lat, cur_lon, candidate.target.latitude, candidate.target.longitude)
        cumulative += distance
        db.add(
            MissionTarget(
                mission_id=mission.id,
                target_id=candidate.target.id,
                sequence=sequence,
                distance_from_previous_m=round(distance, 2),
                cumulative_distance_m=round(cumulative, 2),
            )
        )
        cur_lat, cur_lon = candidate.target.latitude, candidate.target.longitude

    mission.total_distance_m = round(cumulative, 2)
    mission.estimated_duration_s = round(cumulative / speed, 1) if speed > 0 else None
    mission.status = MissionStatus.READY if ordered else MissionStatus.DRAFT

    db.commit()
    db.refresh(mission)
    return mission


def _rankable_candidates(db: Session, survey_id: str) -> list[_Candidate]:
    rows = db.execute(
        select(Target, PriorityScore)
        .join(PriorityScore, PriorityScore.target_id == Target.id)
        .where(Target.survey_id == survey_id)
    ).all()

    candidates: list[_Candidate] = []
    for target, priority in rows:
        if priority.action is PriorityAction.IGNORE:
            continue
        if target.latitude is None or target.longitude is None:
            continue
        candidates.append(_Candidate(target=target, priority=priority))
    return candidates


def _sort_by_priority_then_nearest(
    candidates: list[_Candidate], start_lat: float, start_lon: float
) -> list[_Candidate]:
    # Stable partition by action rank first (VERIFY_NOW before VERIFY_NEXT
    # before VERIFY_LATER); within each rank, greedily visit the nearest
    # unvisited target next.
    remaining = sorted(candidates, key=lambda c: _ACTION_RANK.get(c.priority.action, 99))

    ordered: list[_Candidate] = []
    cur_lat, cur_lon = start_lat, start_lon
    while remaining:
        # Only reorder within the current (highest-remaining) action rank
        # so a VERIFY_NEXT target is never visited before a farther-away
        # VERIFY_NOW target.
        current_rank = _ACTION_RANK.get(remaining[0].priority.action, 99)
        same_rank = [c for c in remaining if _ACTION_RANK.get(c.priority.action, 99) == current_rank]

        nearest = min(
            same_rank,
            key=lambda c: geodesic_distance_m(cur_lat, cur_lon, c.target.latitude, c.target.longitude),
        )
        ordered.append(nearest)
        cur_lat, cur_lon = nearest.target.latitude, nearest.target.longitude
        remaining.remove(nearest)

    return ordered


def get_mission(db: Session, mission_id: str) -> Mission:
    mission = db.get(Mission, mission_id)
    if mission is None:
        raise MissionNotFoundError(f"Mission '{mission_id}' does not exist.", mission_id=mission_id)
    return mission
