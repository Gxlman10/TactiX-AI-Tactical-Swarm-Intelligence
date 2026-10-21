"""Calendar invariants and independently calculated historical summaries."""

import random
from collections import Counter
from itertools import combinations

import pytest
from pydantic import ValidationError

from tactix.domain.universe import Club, Fixture, League
from tactix.universe.generator import LeagueConfig, generate_league
from tactix.universe.history import generate_history, round_robin, validate_history
from tactix.universe.standings import build_head_to_head, build_standings


@pytest.mark.parametrize("count", [8, 9, 10])
@pytest.mark.parametrize("seed", [0, 42, 2026])
def test_round_robin_reverses_venues_after_each_pair_has_met(count, seed):
    ids = [str(i) for i in range(count)]
    schedule = round_robin(ids, seed)
    cycle = count - 1 if count % 2 == 0 else count
    assert len(schedule) == 2 * cycle
    pairs = []
    for day in schedule[:cycle]:
        appearances = [club_id for pair in day for club_id in pair]
        assert len(day) == count // 2
        assert len(set(appearances)) == len(appearances)
        pairs.extend(tuple(sorted(pair)) for pair in day)
    assert Counter(pairs) == Counter(tuple(sorted(pair)) for pair in combinations(ids, 2))
    assert schedule[cycle:] == [[(b, a) for a, b in day] for day in schedule[:cycle]]


@pytest.mark.parametrize("count", [8, 9, 10])
@pytest.mark.parametrize("matchdays", [12, 13, 14])
@pytest.mark.parametrize("seed", [0, 42, 2026])
def test_generated_history_is_coherent(count, matchdays, seed):
    league = generate_league(LeagueConfig(club_count=count, history_matchdays=matchdays, seed=seed))
    validate_history(league)
    assert len(league.fixtures) == (count // 2) * matchdays
    assert len({f.id for f in league.fixtures}) == len(league.fixtures)
    assert len(league.head_to_head) == count * (count - 1) // 2
    assert all(10 <= row.played <= 14 for row in league.standings)
    assert all(row.played == row.won + row.drawn + row.lost for row in league.standings)
    assert all(row.points == 3 * row.won + row.drawn for row in league.standings)
    assert sum(row.played for row in league.standings) == 2 * len(league.fixtures)
    assert (
        sum(row.goals_for for row in league.standings)
        == sum(row.goals_against for row in league.standings)
        == sum(f.home_goals + f.away_goals for f in league.fixtures)
    )
    assert sum(row.won for row in league.standings) == sum(row.lost for row in league.standings)
    assert sum(row.points for row in league.standings) == sum(
        2 if f.home_goals == f.away_goals else 3 for f in league.fixtures
    )
    assert all(len(row.form) == 5 for row in league.standings)
    for record in league.head_to_head:
        matches = [
            f
            for f in league.fixtures
            if {f.home_club_id, f.away_club_id} == {record.club_a_id, record.club_b_id}
        ]
        assert record.wins_a + record.draws + record.wins_b == len(matches)
        assert record.last_result and record.tendencies
    assert League.model_validate_json(league.model_dump_json()) == league


def known_results():
    clubs = [Club(id=key, name=key.upper()) for key in ("a", "b", "c")]
    fixtures = [
        Fixture(id="f1", matchday=1, home_club_id="a", away_club_id="b", home_goals=2),
        Fixture(
            id="f2", matchday=2, home_club_id="c", away_club_id="a", home_goals=1, away_goals=1
        ),
        Fixture(
            id="f3", matchday=3, home_club_id="b", away_club_id="c", home_goals=3, away_goals=1
        ),
        Fixture(id="f4", matchday=4, home_club_id="b", away_club_id="a", away_goals=1),
    ]
    return clubs, fixtures


def test_known_table_form_and_venue_splits():
    clubs, fixtures = known_results()
    rows = build_standings(clubs, list(reversed(fixtures)))
    assert [
        (
            r.club_id,
            r.played,
            r.won,
            r.drawn,
            r.lost,
            r.goals_for,
            r.goals_against,
            r.goal_difference,
            r.points,
            r.form,
        )
        for r in rows
    ] == [
        ("a", 3, 2, 1, 0, 4, 1, 3, 7, ["W", "D", "W"]),
        ("b", 3, 1, 0, 2, 3, 4, -1, 3, ["L", "W", "L"]),
        ("c", 2, 0, 1, 1, 2, 4, -2, 1, ["L", "D"]),
    ]
    home = {r.club_id: r for r in build_standings(clubs, fixtures, "home")}
    away = {r.club_id: r for r in build_standings(clubs, fixtures, "away")}
    assert home["a"].points == 3 and away["a"].points == 4
    for row in rows:
        assert row.points == home[row.club_id].points + away[row.club_id].points
        assert row.played == home[row.club_id].played + away[row.club_id].played


def test_known_head_to_head_orientation_and_latest_result():
    clubs, fixtures = known_results()
    records = {(r.club_a_id, r.club_b_id): r for r in build_head_to_head(clubs, fixtures)}
    ab = records[("a", "b")]
    assert (ab.wins_a, ab.draws, ab.wins_b) == (2, 0, 0)
    assert ab.last_result == "B 0-1 A (matchday 4)"
    assert ab.tendencies == [
        "Both teams scored in 0 of 2 recorded meetings",
        "3 total goals across 2 recorded meetings",
    ]
    ac = records[("a", "c")]
    assert (ac.wins_a, ac.draws, ac.wins_b) == (0, 1, 0)
    assert records[("b", "c")].wins_a == 1


def test_exact_table_tie_is_stable_and_form_keeps_latest_five():
    clubs = [Club(id="b", name="B"), Club(id="a", name="A")]
    fixtures = [
        Fixture(id=str(i), matchday=i, home_club_id="a", away_club_id="b") for i in range(1, 8)
    ]
    rows = build_standings(clubs, fixtures)
    assert [row.club_id for row in rows] == ["a", "b"]
    assert rows[0].form == ["D"] * 5 and rows[0].points == 7


def test_history_reproducibility_and_no_input_mutation():
    base = generate_league(LeagueConfig(generator_version="league-v2"))
    before = random.getstate()
    result = generate_history(base, 42)
    assert result == generate_history(base, 42)
    assert result.fixtures != generate_history(base, 43).fixtures
    assert random.getstate() == before
    assert not base.fixtures and not base.standings


@pytest.mark.parametrize(
    "change",
    [
        "club",
        "scorer",
        "minute",
        "goals",
        "standing",
        "head_to_head",
        "possession",
        "xg",
    ],
)
def test_invalid_history_is_rejected(change):
    league = generate_league()
    fixture = next(f for f in league.fixtures if f.scorers)
    if change == "club":
        fixture.home_club_id = "missing"
    elif change == "scorer":
        fixture.scorers[0].player_id = "missing"
    elif change == "minute":
        fixture.scorers[0].minute = 91
    elif change == "goals":
        fixture.home_goals += 1
    elif change == "standing":
        league.standings[0].points += 1
    elif change == "head_to_head":
        league.head_to_head[0].wins_a += 1
    elif change == "possession":
        fixture.home_possession = 101
    else:
        fixture.home_xg = float("nan")
    with pytest.raises(ValueError):
        validate_history(league)


@pytest.mark.parametrize("value", [11, 15, True, 12.5])
def test_invalid_history_configuration(value):
    with pytest.raises(ValidationError):
        LeagueConfig(history_matchdays=value)


def test_history_requires_rosters_and_rejects_overwriting_history():
    with pytest.raises(ValueError, match="lineup"):
        generate_history(generate_league(LeagueConfig(generator_version="league-v1")), 42)
    with pytest.raises(ValueError, match="existing history"):
        generate_history(generate_league(), 42)
    with pytest.raises(ValidationError, match="requires league-v3"):
        LeagueConfig(generator_version="league-v2", history_matchdays=13)
