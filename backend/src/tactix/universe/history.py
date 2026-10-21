"""Synthetic previous fixtures, not a replacement for live event simulation."""

import hashlib
import math
import random
from uuid import NAMESPACE_URL, uuid5

from tactix.domain.enums import BuildUpStyle, Position
from tactix.domain.universe import Club, Fixture, League, Player, Scorer
from tactix.universe.standings import build_head_to_head, build_standings, ordered_fixtures


def round_robin(club_ids: list[str], seed: int) -> list[list[tuple[str, str]]]:
    """Double round robin, reversing venues after the first complete cycle."""
    if len(club_ids) < 2 or len(set(club_ids)) != len(club_ids):
        raise ValueError("At least two unique clubs are required")
    rotation: list[str | None] = list(club_ids)
    random.Random(seed).shuffle(rotation)
    if len(rotation) % 2:
        rotation.append(None)
    first_leg = []
    for day in range(len(rotation) - 1):
        pairs = []
        for index in range(len(rotation) // 2):
            home, away = rotation[index], rotation[-index - 1]
            if index == 0 and day % 2:
                home, away = away, home
            if home is not None and away is not None:
                pairs.append((home, away))
        first_leg.append(pairs)
        rotation = [rotation[0], rotation[-1], *rotation[1:-1]]
    return first_leg + [[(away, home) for home, away in pairs] for pairs in first_leg]


def _starters(club: Club) -> list[Player]:
    if len(club.squad) < 11 or any(not p.positions for p in club.squad[:11]):
        raise ValueError("Historical simulation requires an eleven-player starting lineup")
    if sum(Position.GK in p.positions for p in club.squad[:11]) != 1:
        raise ValueError("Historical simulation requires exactly one starting goalkeeper")
    return [p for p in club.squad[:11] if Position.GK not in p.positions]


def _shots(
    club: Club,
    opponent: Club,
    rng: random.Random,
    home: bool,
) -> tuple[int, float, list[Scorer]]:
    attackers, defenders = _starters(club), _starters(opponent)
    defence = sum((p.mental.marking + p.mental.positioning) / 2 for p in defenders) / 10
    keeper = next(p for p in opponent.squad[:11] if Position.GK in p.positions)
    if keeper.goalkeeping is None:
        raise ValueError("Starting goalkeeper is missing goalkeeper attributes")
    shot_count = max(4, rng.randint(7, 15) + round((club.tactical_identity.tempo - 50) / 20))
    total_xg, scorers = 0.0, []
    for _ in range(shot_count):
        shooter = rng.choices(
            attackers,
            weights=[p.technical.finishing**2 + p.mental.positioning * 10 for p in attackers],
            k=1,
        )[0]
        chance = max(
            0.02,
            min(
                0.45,
                rng.uniform(0.04, 0.24)
                + (shooter.technical.finishing - defence) / 450
                + (65 - keeper.goalkeeping.reflexes) / 600
                + (0.015 if home else 0),
            ),
        )
        total_xg += chance
        minute = rng.randint(1, 90)
        if rng.random() < chance:
            scorers.append(Scorer(player_id=shooter.id, club_id=club.id, minute=minute))
    return shot_count, round(total_xg, 3), scorers


def generate_history(league: League, seed: int, matchdays: int = 12) -> League:
    if type(seed) is not int or not 0 <= seed <= 2**63 - 1:
        raise ValueError("seed must be an integer between 0 and 2^63-1")
    if type(matchdays) is not int or not 12 <= matchdays <= 14:
        raise ValueError("matchdays must be an integer between 12 and 14")
    if league.fixtures or league.standings or league.head_to_head:
        raise ValueError("History must be generated from a league without existing history")
    if not 8 <= len(league.clubs) <= 10:
        raise ValueError("Historical context requires 8–10 clubs")
    clubs = {club.id: club for club in league.clubs}
    for club in league.clubs:
        _starters(club)
    schedule = round_robin([club.id for club in league.clubs], seed)
    namespace = uuid5(NAMESPACE_URL, f"tactix:history-v1:{league.id}:{seed}")
    fixtures = []
    for day, pairs in enumerate(schedule[:matchdays], start=1):
        for home_id, away_id in pairs:
            home, away = clubs[home_id], clubs[away_id]
            fixture_id = uuid5(namespace, f"{day}:{home_id}:{away_id}")
            rng = random.Random(int.from_bytes(hashlib.sha256(str(fixture_id).encode()).digest()))
            home_shots, home_xg, home_scorers = _shots(home, away, rng, True)
            away_shots, away_xg, away_scorers = _shots(away, home, rng, False)
            scorers = sorted(home_scorers + away_scorers, key=lambda scorer: scorer.minute)
            home_passing = sum(p.technical.passing for p in _starters(home)) / 10
            away_passing = sum(p.technical.passing for p in _starters(away)) / 10
            home_bias = 5 if home.tactical_identity.build_up == BuildUpStyle.SHORT else 0
            away_bias = 5 if away.tactical_identity.build_up == BuildUpStyle.SHORT else 0
            possession = max(
                30,
                min(
                    70,
                    53
                    + (home_passing - away_passing) / 2
                    + home_bias
                    - away_bias
                    + rng.uniform(-5, 5),
                ),
            )
            first = scorers[0] if scorers else None
            fixtures.append(
                Fixture(
                    id=str(fixture_id),
                    matchday=day,
                    home_club_id=home_id,
                    away_club_id=away_id,
                    home_goals=len(home_scorers),
                    away_goals=len(away_scorers),
                    scorers=scorers,
                    home_formation=home.tactical_identity.formation,
                    away_formation=away.tactical_identity.formation,
                    home_xg=home_xg,
                    away_xg=away_xg,
                    home_possession=round(possession, 2),
                    key_events=[
                        f"Synthetic shots: {home.name} {home_shots}; {away.name} {away_shots}",
                        *[f"Goal: {scorer.player_id}, {scorer.minute}'" for scorer in scorers],
                    ],
                    pattern_note=(
                        f"{clubs[first.club_id].name} scored first in minute {first.minute}"
                        if first
                        else "Neither team scored in this recorded fixture"
                    ),
                )
            )
    result = league.model_copy(deep=True)
    result.fixtures = fixtures
    result.standings = build_standings(result.clubs, fixtures)
    result.head_to_head = build_head_to_head(result.clubs, fixtures)
    validate_history(result)
    return result


def validate_history(league: League) -> None:
    """Reject broken references or summaries that disagree with the fixture ledger."""
    fixtures = ordered_fixtures(league.clubs, league.fixtures)
    if not fixtures:
        if league.standings or league.head_to_head:
            raise ValueError("League history summaries require supporting fixtures")
        return
    players = {c.id: {p.id for p in c.squad} for c in league.clubs}
    for fixture in fixtures:
        if (
            not (math.isfinite(fixture.home_xg) and math.isfinite(fixture.away_xg))
            or min(fixture.home_xg, fixture.away_xg) < 0
        ):
            raise ValueError("xG-like values must be finite and nonnegative")
        if not 0 <= fixture.home_possession <= 100:
            raise ValueError("Possession must be between 0 and 100")
        for scorer in fixture.scorers:
            if scorer.club_id not in (fixture.home_club_id, fixture.away_club_id):
                raise ValueError("Scorer belongs to a club outside the fixture")
            if scorer.player_id not in players[scorer.club_id] or not 1 <= scorer.minute <= 90:
                raise ValueError("Scorer must belong to its club and have a valid minute")
        if sum(s.club_id == fixture.home_club_id for s in fixture.scorers) != fixture.home_goals:
            raise ValueError("Home goals do not match scorer records")
        if sum(s.club_id == fixture.away_club_id for s in fixture.scorers) != fixture.away_goals:
            raise ValueError("Away goals do not match scorer records")
    if league.standings != build_standings(league.clubs, fixtures):
        raise ValueError("Standings disagree with history fixtures")
    if league.head_to_head != build_head_to_head(league.clubs, fixtures):
        raise ValueError("Head-to-head records disagree with history fixtures")
