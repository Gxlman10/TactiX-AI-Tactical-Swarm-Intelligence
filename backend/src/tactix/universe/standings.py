"""Rebuild all season summaries from the same chronological fixture ledger."""

from itertools import combinations
from typing import Literal

from tactix.domain.universe import Club, Fixture, HeadToHead, StandingRow


def ordered_fixtures(clubs: list[Club], fixtures: list[Fixture]) -> list[Fixture]:
    club_ids = {club.id for club in clubs}
    if len(club_ids) != len(clubs):
        raise ValueError("Club IDs must be unique")
    fixture_ids, appearances = set(), set()
    for fixture in fixtures:
        if fixture.id in fixture_ids:
            raise ValueError("Duplicate fixture ID")
        fixture_ids.add(fixture.id)
        if fixture.home_club_id not in club_ids or fixture.away_club_id not in club_ids:
            raise ValueError("Fixture references an unknown club")
        if fixture.home_club_id == fixture.away_club_id:
            raise ValueError("A club cannot play itself")
        if fixture.matchday < 1 or min(fixture.home_goals, fixture.away_goals) < 0:
            raise ValueError("Matchday must be positive and goals nonnegative")
        for club_id in (fixture.home_club_id, fixture.away_club_id):
            key = (fixture.matchday, club_id)
            if key in appearances:
                raise ValueError("A club cannot play twice on one matchday")
            appearances.add(key)
    return sorted(fixtures, key=lambda fixture: (fixture.matchday, fixture.id))


def build_standings(
    clubs: list[Club],
    fixtures: list[Fixture],
    venue: Literal["all", "home", "away"] = "all",
) -> list[StandingRow]:
    if venue not in ("all", "home", "away"):
        raise ValueError("venue must be all, home or away")
    rows = {club.id: StandingRow(club_id=club.id) for club in clubs}
    for fixture in ordered_fixtures(clubs, fixtures):
        sides = (
            (fixture.home_club_id, fixture.home_goals, fixture.away_goals, "home"),
            (fixture.away_club_id, fixture.away_goals, fixture.home_goals, "away"),
        )
        for club_id, scored, conceded, side in sides:
            if venue != "all" and venue != side:
                continue
            row = rows[club_id]
            row.played += 1
            row.goals_for += scored
            row.goals_against += conceded
            result = "W" if scored > conceded else "L" if scored < conceded else "D"
            row.won += result == "W"
            row.drawn += result == "D"
            row.lost += result == "L"
            row.points += 3 if result == "W" else 1 if result == "D" else 0
            row.form = [result, *row.form[:4]]
    # Synthetic competition rule: points, GD, GF; stable ID breaks exact ties.
    return sorted(
        rows.values(),
        key=lambda row: (-row.points, -row.goal_difference, -row.goals_for, row.club_id),
    )


def build_head_to_head(clubs: list[Club], fixtures: list[Fixture]) -> list[HeadToHead]:
    ordered = ordered_fixtures(clubs, fixtures)
    names = {club.id: club.name for club in clubs}
    records = []
    for first, second in combinations(clubs, 2):
        matches = [
            fixture
            for fixture in ordered
            if {fixture.home_club_id, fixture.away_club_id} == {first.id, second.id}
        ]
        record = HeadToHead(club_a_id=first.id, club_b_id=second.id)
        for fixture in matches:
            home, away = fixture.home_goals, fixture.away_goals
            if home == away:
                record.draws += 1
            elif (home > away) == (fixture.home_club_id == first.id):
                record.wins_a += 1
            else:
                record.wins_b += 1
        if matches:
            last = matches[-1]
            record.last_result = (
                f"{names[last.home_club_id]} {last.home_goals}-{last.away_goals} "
                f"{names[last.away_club_id]} (matchday {last.matchday})"
            )
            both = sum(f.home_goals > 0 and f.away_goals > 0 for f in matches)
            goals = sum(f.home_goals + f.away_goals for f in matches)
            record.tendencies = [
                f"Both teams scored in {both} of {len(matches)} recorded meetings",
                f"{goals} total goals across {len(matches)} recorded meetings",
            ]
        records.append(record)
    return records
