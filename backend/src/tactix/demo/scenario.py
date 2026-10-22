"""Versioned authored overlay preserving the surrounding procedural match."""

from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel

from tactix.demo.evidence import PatternEvidence, midfield_concessions, seconds
from tactix.domain.common import Point
from tactix.domain.enums import EventType, Outcome, Position, PossessionPhase, ShotOutcome
from tactix.domain.events import Event, Possession
from tactix.domain.universe import Club, Fixture, League, Scorer
from tactix.metrics.advanced import advanced_metrics_for_match
from tactix.simulation.engine import MatchResult, PossessionFrame, simulate_match
from tactix.simulation.rules import direction, distance, mirror, pitch_zone, shot_angle, shot_value
from tactix.simulation.validation import validate_match
from tactix.universe.generator import generate_league
from tactix.universe.history import validate_history
from tactix.universe.standings import build_head_to_head, build_standings

SCENARIO_VERSION = "ashford-demo-v1"
CLIMAX_SECOND = 3720


class DemoBundle(BaseModel):
    scenario_version: str = SCENARIO_VERSION
    league: League
    historical_matches: dict[str, MatchResult]
    live: MatchResult
    climax_goal_id: str


def _identity(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"tactix:{SCENARIO_VERSION}:{value}"))


def _overlay(
    home: Club, away: Club, vulnerable: Club, scorer_id: str, match_id: str
) -> tuple[MatchResult, str]:
    result = simulate_match(home, away).model_copy(deep=True)
    ids = {e.id: _identity(f"{match_id}:{e.id}") for e in result.events}
    result.match_id = match_id
    for frame in result.frames:
        p = frame.possession
        p.id, p.match_id = _identity(f"{match_id}:{p.id}"), match_id
        p.event_ids = [ids[key] for key in p.event_ids]
        for event in frame.events:
            event.id, event.match_id, event.possession_id = ids[event.id], match_id, p.id
            if event.type == EventType.GOAL:
                event.subtype = "from_shot:" + ids[event.subtype.removeprefix("from_shot:")]
    rival = away if vulnerable.id == home.id else home
    defender = next(p for p in rival.squad[:11] if Position.GK not in p.positions)
    first_index = max(
        i
        for i, f in enumerate(result.frames)
        if f.possession.team_id == vulnerable.id
        and 2700 <= seconds(f.events[0]) <= CLIMAX_SECOND - 28
    )
    resume_index = next(
        i
        for i, f in enumerate(result.frames)
        if i > first_index
        and f.possession.team_id == vulnerable.id
        and seconds(f.events[0]) >= CLIMAX_SECOND + 8
    )
    original_first = result.frames[first_index].events[0].model_copy(deep=True)
    carrier = next(
        p
        for p in vulnerable.squad[:11]
        if Position.GK not in p.positions and p.id != original_first.player_id
    )

    def event(key, at, club, player, kind, start, end=None, **kwargs):
        return Event(
            id=_identity(f"{match_id}:script:{key}"),
            match_id=match_id,
            minute=at // 60,
            second=at % 60,
            team_id=club.id,
            player_id=player,
            type=kind,
            start=start,
            end=end,
            pitch_zone=pitch_zone(start),
            distance=distance(start, end) if end else None,
            angle=(shot_angle(start) if kind == EventType.SHOT else direction(start, end))
            if end
            else None,
            progressive=end.x - start.x >= 10
            if end and kind in (EventType.PASS, EventType.CARRY, EventType.DRIBBLE)
            else False,
            **kwargs,
        )

    def frame(key, club, events, outcome, ended=None):
        p_id = _identity(f"{match_id}:script:possession:{key}")
        for e in events:
            e.possession_id = p_id
        end = ended if ended is not None else seconds(events[-1])
        return PossessionFrame(
            possession=Possession(
                id=p_id,
                match_id=match_id,
                team_id=club.id,
                start_minute=events[0].minute,
                start_second=events[0].second,
                end_minute=end // 60,
                end_second=end % 60,
                phase=PossessionPhase.OUTCOME,
                event_ids=[e.id for e in events],
                outcome=outcome,
            ),
            phases=list(PossessionPhase),
            events=events,
        )

    centre, lost_at, recovery_at = Point(x=50, y=50), Point(x=55, y=50), Point(x=45, y=50)
    loss_events = [
        original_first,
        event(
            "support",
            CLIMAX_SECOND - 24,
            vulnerable,
            original_first.player_id,
            EventType.PASS,
            original_first.start,
            centre,
            related_player_id=carrier.id,
        ),
        event(
            "pressure",
            CLIMAX_SECOND - 20,
            rival,
            defender.id,
            EventType.PRESS,
            mirror(centre),
            related_player_id=carrier.id,
        ),
        event(
            "loss",
            CLIMAX_SECOND - 20,
            vulnerable,
            carrier.id,
            EventType.PASS,
            centre,
            lost_at,
            related_player_id=original_first.player_id,
            outcome=Outcome.FAIL,
            under_pressure=True,
            pressured_by=defender.id,
        ),
    ]
    # The chosen scorer must be distinct from the recovering passer.
    if defender.id == scorer_id:
        defender = next(
            p for p in rival.squad[:11] if Position.GK not in p.positions and p.id != scorer_id
        )
        loss_events[-2].player_id = defender.id
        loss_events[-1].pressured_by = defender.id
    shot_at = Point(x=82, y=25)
    shot = event(
        "shot",
        CLIMAX_SECOND,
        rival,
        scorer_id,
        EventType.SHOT,
        shot_at,
        Point(x=100, y=50),
        expected_value=shot_value(shot_at),
        shot_outcome=ShotOutcome.GOAL,
    )
    goal = event(
        "goal",
        CLIMAX_SECOND,
        rival,
        scorer_id,
        EventType.GOAL,
        shot_at,
        subtype=f"from_shot:{shot.id}",
    )
    attack_events = [
        event("recovery", CLIMAX_SECOND - 12, rival, defender.id, EventType.RECOVERY, recovery_at),
        event(
            "assist-pass",
            CLIMAX_SECOND - 6,
            rival,
            defender.id,
            EventType.PASS,
            recovery_at,
            shot_at,
            related_player_id=scorer_id,
        ),
        shot,
        goal,
    ]
    # Reconnect to the untouched suffix through a proper conceding-team kickoff.
    resume = result.frames[resume_index].model_copy(deep=True)
    receiver = resume.events[0]
    kicker = next(
        p
        for p in vulnerable.squad[:11]
        if Position.GK not in p.positions and p.id != receiver.player_id
    )
    restart_events = [
        event("kickoff", CLIMAX_SECOND + 8, vulnerable, kicker.id, EventType.KICKOFF, centre),
        event(
            "restart-pass",
            CLIMAX_SECOND + 9,
            vulnerable,
            kicker.id,
            EventType.PASS,
            centre,
            receiver.start,
            related_player_id=receiver.player_id,
        ),
        *resume.events[1:],
    ]
    restart = frame(
        "restart",
        vulnerable,
        restart_events,
        resume.possession.outcome,
        resume.possession.end_minute * 60 + resume.possession.end_second,
    )
    result.frames = [
        *result.frames[:first_index],
        frame("loss", vulnerable, loss_events, "turnover"),
        frame("attack", rival, attack_events, "goal"),
        restart,
        *result.frames[resume_index + 1 :],
    ]
    validate_match(result, home, away)
    advanced_metrics_for_match(result)
    return result, goal.id


def _fixture(source: Fixture, result: MatchResult, home: Club, away: Club) -> Fixture:
    snapshot = advanced_metrics_for_match(result)
    metrics = [{v.key: v.value for v in team.values} for team in snapshot.teams]
    return Fixture(
        id=result.match_id,
        matchday=source.matchday,
        home_club_id=home.id,
        away_club_id=away.id,
        home_goals=result.score[0],
        away_goals=result.score[1],
        scorers=[
            Scorer(player_id=e.player_id, club_id=e.team_id, minute=e.minute)
            for e in result.events
            if e.type == EventType.GOAL
        ],
        home_formation=home.tactical_identity.formation,
        away_formation=away.tactical_identity.formation,
        home_xg=metrics[0]["xg_like"],
        away_xg=metrics[1]["xg_like"],
        home_possession=metrics[0]["possession_pct"],
        key_events=[
            f"Goal event {e.id}: {e.player_id} at {e.minute}:{e.second:02}"
            for e in result.events
            if e.type == EventType.GOAL
        ],
        pattern_note="Authored synthetic demo; event-backed midfield turnover concession",
    )


def build_demo() -> DemoBundle:
    league = generate_league().model_copy(deep=True)
    league.id = _identity(league.id)
    clubs = {c.id: c for c in league.clubs}
    ashford = next(c for c in league.clubs if c.name == "Ashford")
    northbridge = next(c for c in league.clubs if c.name == "Northbridge")
    ashford_fixtures = sorted(
        [f for f in league.fixtures if ashford.id in (f.home_club_id, f.away_club_id)],
        key=lambda f: f.matchday,
    )
    prior_meeting = next(
        f for f in ashford_fixtures if northbridge.id in (f.home_club_id, f.away_club_id)
    )
    chosen = {f.id for f in [*ashford_fixtures[-3:], prior_meeting]}
    historical = {}
    fixtures = []
    for fixture in league.fixtures:
        old_id = fixture.id
        fixture.id = _identity(old_id)
        if old_id in chosen:
            home, away = clubs[fixture.home_club_id], clubs[fixture.away_club_id]
            rival = away if home.id == ashford.id else home
            scorer = next(p for p in rival.squad[:11] if Position.ST in p.positions)
            result, _ = _overlay(home, away, ashford, scorer.id, fixture.id)
            historical[fixture.id] = result
            fixture = _fixture(fixture, result, home, away)
        fixtures.append(fixture)
    league.fixtures = fixtures
    league.standings = build_standings(league.clubs, fixtures)
    league.head_to_head = build_head_to_head(league.clubs, fixtures)
    validate_history(league)
    hartley = next(p for p in northbridge.squad if p.name == "Finn Hartley")
    live, goal_id = _overlay(
        ashford, northbridge, ashford, hartley.id, _identity("live:Ashford:Northbridge")
    )
    return DemoBundle(
        league=league, historical_matches=historical, live=live, climax_goal_id=goal_id
    )


class DemoContext(BaseModel):
    scenario_version: str = SCENARIO_VERSION
    revision: int = 0
    at_second: int
    historical_patterns: dict[str, list[PatternEvidence]]
    climax: PatternEvidence | None
    verified_consecutive_matches: int
    scorer_season_goals: int
    scorer_fixture_ids: list[str]
    scorer_live_goal_ids: list[str]
    earlier_meeting_fixture_ids: list[str]
    preview: str | None


def demo_context(bundle: DemoBundle, at_second: int) -> DemoContext:
    ashford, northbridge = bundle.live.home_club_id, bundle.live.away_club_id
    hartley = next(
        p
        for c in bundle.league.clubs
        if c.id == northbridge
        for p in c.squad
        if p.name == "Finn Hartley"
    )
    history = {
        key: midfield_concessions(match, ashford)
        for key, match in bundle.historical_matches.items()
    }
    live = midfield_concessions(bundle.live, ashford, at_second)
    climax = next((p for p in live if bundle.climax_goal_id in p.event_ids), None)
    fixtures = sorted(
        [f for f in bundle.league.fixtures if ashford in (f.home_club_id, f.away_club_id)],
        key=lambda f: f.matchday,
    )
    streak = 0
    for fixture in reversed(fixtures):
        if not history.get(fixture.id):
            break
        streak += 1
    goals = [
        (f.id, s) for f in bundle.league.fixtures for s in f.scorers if s.player_id == hartley.id
    ]
    visible_goals = [
        e.id
        for e in bundle.live.events
        if e.type == EventType.GOAL and e.player_id == hartley.id and seconds(e) <= at_second
    ]
    count = len(goals) + len(visible_goals)
    verified = streak + int(climax is not None)
    meetings = sorted(
        key
        for key, patterns in history.items()
        if any(p.scoring_club_id == northbridge for p in patterns)
    )
    preview = (
        (
            f"Goal by {hartley.name}, {climax.goal_second // 60}:{climax.goal_second % 60:02}, "
            f"from the {climax.shot_channel} channel. "
            f"He has {count} goals in the recorded season. Ashford conceded "
            f"{climax.elapsed_seconds} seconds after losing the ball in midfield; "
            f"that pattern appears in each of their last {verified} matches, "
            "including this one."
            + (" The same pattern appears in the earlier Northbridge meeting." if meetings else "")
        )
        if climax
        else None
    )
    return DemoContext(
        at_second=at_second,
        historical_patterns=history,
        climax=climax,
        verified_consecutive_matches=verified,
        scorer_season_goals=count,
        scorer_fixture_ids=sorted({key for key, _ in goals}),
        scorer_live_goal_ids=visible_goals,
        earlier_meeting_fixture_ids=meetings,
        preview=preview,
    )
