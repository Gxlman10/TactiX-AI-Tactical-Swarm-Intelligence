"""Deterministic turnover-to-goal evidence, independent of narrative labels."""

from pydantic import BaseModel

from tactix.domain.enums import EventType, Outcome, ShotOutcome
from tactix.simulation.engine import MatchResult
from tactix.simulation.rules import mirror


class PatternEvidence(BaseModel):
    match_id: str
    possession_ids: list[str]
    event_ids: list[str]
    conceding_club_id: str
    scoring_club_id: str
    scorer_id: str
    loss_second: int
    goal_second: int
    elapsed_seconds: int
    shot_channel: str


def seconds(event) -> int:
    return event.minute * 60 + event.second


def midfield_concessions(
    result: MatchResult, club_id: str, at_second: int = 5400
) -> list[PatternEvidence]:
    """Failed central-third action -> rival recovery -> goal within 30 seconds.

    Only adjacent possessions qualify. The loss must be in x=[40,60], the recovery
    must follow it, and the goal must reference its scoring shot. A pattern_note
    or event subtype label cannot fabricate a detected occurrence.
    """
    if type(at_second) is not int or not 0 <= at_second <= result.config.duration_minutes * 60:
        raise ValueError("Evidence cutoff must be an integer inside the match")
    if club_id not in (result.home_club_id, result.away_club_id):
        raise ValueError("Unknown conceding club")
    patterns = []
    for loss_frame, attack_frame in zip(result.frames, result.frames[1:], strict=False):
        if (
            loss_frame.possession.team_id != club_id
            or loss_frame.possession.outcome != "turnover"
            or attack_frame.possession.team_id == club_id
        ):
            continue
        loss = loss_frame.events[-1]
        recovery = attack_frame.events[0]
        if (
            loss.type not in (EventType.PASS, EventType.CARRY, EventType.DRIBBLE)
            or loss.outcome != Outcome.FAIL
            or not 40 <= loss.start.x <= 60
            or recovery.type != EventType.RECOVERY
            or loss.end is None
            or recovery.start != mirror(loss.end)
            or seconds(recovery) < seconds(loss)
        ):
            continue
        shots = {e.id: e for e in attack_frame.events if e.type == EventType.SHOT}
        for goal in attack_frame.events:
            shot = shots.get((goal.subtype or "").removeprefix("from_shot:"))
            if (
                goal.type != EventType.GOAL
                or shot is None
                or not (goal.subtype or "").startswith("from_shot:")
                or shot.shot_outcome != ShotOutcome.GOAL
                or (goal.team_id, goal.player_id, seconds(goal))
                != (shot.team_id, shot.player_id, seconds(shot))
                or goal.team_id != attack_frame.possession.team_id
                or recovery.team_id != attack_frame.possession.team_id
                or not seconds(recovery) <= seconds(goal) <= min(at_second, seconds(loss) + 30)
            ):
                continue
            patterns.append(
                PatternEvidence(
                    match_id=result.match_id,
                    possession_ids=[loss_frame.possession.id, attack_frame.possession.id],
                    event_ids=[loss.id, recovery.id, shot.id, goal.id],
                    conceding_club_id=club_id,
                    scoring_club_id=goal.team_id,
                    scorer_id=goal.player_id,
                    loss_second=seconds(loss),
                    goal_second=seconds(goal),
                    elapsed_seconds=seconds(goal) - seconds(loss),
                    shot_channel="left"
                    if shot.start.y < 100 / 3
                    else ("right" if shot.start.y >= 200 / 3 else "central"),
                )
            )
    return patterns
