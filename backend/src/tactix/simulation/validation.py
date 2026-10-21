"""Validate simulation artifacts before handing them to metrics or replay."""

from __future__ import annotations

import math
from collections import Counter
from typing import TYPE_CHECKING

from tactix.domain.enums import EventType, Outcome, Position, PossessionPhase, ShotOutcome
from tactix.domain.universe import Club
from tactix.simulation.rules import direction, distance, pitch_zone, shot_angle, shot_value

if TYPE_CHECKING:
    from tactix.simulation.engine import MatchResult


def validate_match(result: MatchResult, home: Club, away: Club) -> None:
    if (result.home_club_id, result.away_club_id) != (home.id, away.id) or home.id == away.id:
        raise ValueError("Match clubs do not match the source lineups")
    clubs = {club.id: {p.id: p for p in club.squad[:11]} for club in (home, away)}
    all_players = {key for players in clubs.values() for key in players}
    events = result.events
    if not events or not result.frames:
        raise ValueError("A match must contain possessions and events")
    if len({e.id for e in events}) != len(events):
        raise ValueError("Event IDs must be unique")
    if len({f.possession.id for f in result.frames}) != len(result.frames):
        raise ValueError("Possession IDs must be unique")
    times = [e.minute * 60 + e.second for e in events]
    if times != sorted(times):
        raise ValueError("Events must be chronological")
    maximum = result.config.duration_minutes * 60
    half = maximum // 2
    openers = [(home.id, 0), (away.id, half)]
    for team, when in openers:
        if not any(
            e.type == EventType.KICKOFF and e.team_id == team and e.minute * 60 + e.second == when
            for e in events
        ):
            raise ValueError("Each period must start with the designated kickoff")
    paths = [
        [PossessionPhase.BUILD_UP, PossessionPhase.OUTCOME],
        [PossessionPhase.BUILD_UP, PossessionPhase.PROGRESSION, PossessionPhase.OUTCOME],
        list(PossessionPhase),
    ]
    previous_end = 0
    for frame in result.frames:
        possession = frame.possession
        began = possession.start_minute * 60 + possession.start_second
        ended = possession.end_minute * 60 + possession.end_second
        if not previous_end <= began <= ended <= maximum:
            raise ValueError("Possession windows must not overlap or exceed the match")
        previous_end = ended
        if began < half < ended:
            raise ValueError("A possession cannot cross halftime")
        if possession.match_id != result.match_id or possession.team_id not in clubs:
            raise ValueError("Invalid possession ownership")
        if frame.phases not in paths or possession.phase != PossessionPhase.OUTCOME:
            raise ValueError("Invalid possession state path")
        if not frame.events or possession.event_ids != [e.id for e in frame.events]:
            raise ValueError("Possession event links must match its actual events")
        for event in frame.events:
            if event.possession_id != possession.id or event.match_id != result.match_id:
                raise ValueError("Event links reference a different match or possession")
            if event.team_id not in clubs or event.player_id not in clubs[event.team_id]:
                raise ValueError("Event player must belong to the acting starting lineup")
            defensive = event.type in (
                EventType.PRESS,
                EventType.SAVE,
                EventType.BLOCK,
                EventType.FOUL,
            )
            if (event.team_id == possession.team_id) == defensive:
                raise ValueError("Acting team disagrees with the event's possession role")
            if defensive and event.related_player_id not in clubs[possession.team_id]:
                raise ValueError("Defensive action must reference the opposing ball carrier")
            if not began <= event.minute * 60 + event.second <= ended:
                raise ValueError("Event timestamp must be inside its possession")
            if not 0 <= event.second < 60:
                raise ValueError("Event seconds must be normalized")
            if event.related_player_id is not None and event.related_player_id not in all_players:
                raise ValueError("Related player is unknown")
            if event.under_pressure != (event.pressured_by is not None):
                raise ValueError("Pressure flag and opponent reference disagree")
            if event.pressured_by is not None and (
                event.pressured_by not in all_players or event.pressured_by in clubs[event.team_id]
            ):
                raise ValueError("Pressure must come from an opposing player")
            if event.pitch_zone != pitch_zone(event.start):
                raise ValueError("Pitch zone disagrees with coordinates")
            if event.type != EventType.SHOT and (
                event.expected_value is not None or event.shot_outcome is not None
            ):
                raise ValueError("Only shot events may carry shot outcomes or expected values")
            if event.end is not None:
                expected_angle = (
                    shot_angle(event.start)
                    if event.type == EventType.SHOT
                    else direction(event.start, event.end)
                )
                if (
                    event.distance is None
                    or not math.isclose(
                        event.distance, distance(event.start, event.end), abs_tol=0.0001
                    )
                    or event.angle is None
                    or not math.isclose(event.angle, expected_angle, abs_tol=1e-8)
                ):
                    raise ValueError("Distance or angle disagrees with coordinates")
            if event.type == EventType.PASS and (
                event.related_player_id not in clubs[event.team_id]
                or event.related_player_id == event.player_id
                or event.end is None
            ):
                raise ValueError("A pass needs a distinct teammate receiver and destination")
            if event.type in (EventType.PASS, EventType.CARRY, EventType.DRIBBLE) and (
                event.end is None or event.progressive != (event.end.x - event.start.x >= 10)
            ):
                raise ValueError("Progressive qualifier disagrees with ball movement")
            if event.type in (EventType.SAVE, EventType.GOAL_KICK) and Position.GK not in (
                clubs[event.team_id][event.player_id].positions
            ):
                raise ValueError("A goalkeeper action must be assigned to the goalkeeper")
            if event.type == EventType.SHOT and (
                event.shot_outcome is None
                or event.expected_value != shot_value(event.start)
                or event.end is None
            ):
                raise ValueError("A shot needs its outcome and coordinate-based expected value")
        shots = {event.id: event for event in frame.events if event.type == EventType.SHOT}
        goal_links = Counter()
        for event in frame.events:
            if event.type == EventType.GOAL:
                source_id = (event.subtype or "").removeprefix("from_shot:")
                source = shots.get(source_id)
                if (
                    not (event.subtype or "").startswith("from_shot:")
                    or source is None
                    or source.shot_outcome != ShotOutcome.GOAL
                    or (source.team_id, source.player_id, source.minute, source.second)
                    != (event.team_id, event.player_id, event.minute, event.second)
                ):
                    raise ValueError("A goal must reference a scoring shot by the same player")
                goal_links[source_id] += 1
        for shot in shots.values():
            if goal_links[shot.id] != int(shot.shot_outcome == ShotOutcome.GOAL):
                raise ValueError("Each scoring shot must produce exactly one goal")
            if (shot.outcome == Outcome.SUCCESS) != (shot.shot_outcome == ShotOutcome.GOAL):
                raise ValueError("Shot success flag disagrees with shot outcome")
    outcomes = {
        "goal": (False, EventType.KICKOFF),
        "turnover": (False, EventType.RECOVERY),
        "clearance": (False, EventType.RECOVERY),
        "blocked": (False, EventType.RECOVERY),
        "saved": (False, EventType.GOAL_KICK),
        "off_target": (False, EventType.GOAL_KICK),
        "corner": (True, EventType.CORNER),
        "foul_won": (True, EventType.FREE_KICK),
    }
    for index, frame in enumerate(result.frames):
        outcome = frame.possession.outcome
        if outcome == "period_end":
            if frame.possession.end_minute * 60 + frame.possession.end_second not in (
                half,
                maximum,
            ):
                raise ValueError("Period-end possession must terminate at a period boundary")
            continue
        if outcome not in outcomes:
            raise ValueError("Unknown possession outcome")
        terminal = frame.events[-1]
        expected_terminal = {
            "goal": EventType.GOAL,
            "saved": EventType.SAVE,
            "off_target": EventType.SHOT,
            "corner": EventType.BLOCK,
            "blocked": EventType.BLOCK,
            "foul_won": EventType.FOUL,
            "clearance": EventType.CLEARANCE,
        }
        if outcome in expected_terminal and terminal.type != expected_terminal[outcome]:
            raise ValueError("Possession outcome disagrees with its terminal event")
        if outcome == "turnover" and (
            terminal.type not in (EventType.PASS, EventType.CARRY, EventType.DRIBBLE)
            or terminal.outcome != Outcome.FAIL
        ):
            raise ValueError("A turnover must end in a failed ball action")
        if index + 1 == len(result.frames):
            continue
        following = result.frames[index + 1]
        first = following.events[0]
        if first.type == EventType.KICKOFF and first.minute * 60 + first.second == half:
            continue
        same_team, restart = outcomes[outcome]
        if (
            following.possession.team_id == frame.possession.team_id
        ) != same_team or first.type != restart:
            raise ValueError("Restart or possession ownership disagrees with the preceding outcome")
