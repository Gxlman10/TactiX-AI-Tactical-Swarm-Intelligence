"""Save and load league rosters without changing the domain contracts."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from tactix.domain.universe import Club, Fixture, League, Player
from tactix.persistence.models import ClubRecord, FixtureRecord, LeagueRecord, PlayerRecord
from tactix.universe.history import validate_history
from tactix.universe.standings import build_head_to_head, build_standings


def add_league(session: Session, league: League) -> None:
    """Insert an aggregate atomically; validate derived summaries before adding it."""
    validate_history(league)
    session.add(
        LeagueRecord(
            id=league.id,
            name=league.name,
            season=league.season,
            has_history=bool(league.fixtures),
            fixtures=[
                FixtureRecord(
                    id=f.id,
                    league_id=league.id,
                    position=i,
                    matchday=f.matchday,
                    home_club_id=f.home_club_id,
                    away_club_id=f.away_club_id,
                    home_goals=f.home_goals,
                    away_goals=f.away_goals,
                    details=f.model_dump(
                        mode="json",
                        exclude={
                            "id",
                            "matchday",
                            "home_club_id",
                            "away_club_id",
                            "home_goals",
                            "away_goals",
                        },
                    ),
                )
                for i, f in enumerate(league.fixtures)
            ],
            clubs=[
                ClubRecord(
                    id=club.id,
                    league_id=league.id,
                    position=i,
                    name=club.name,
                    details=club.model_dump(mode="json", exclude={"id", "name", "squad"}),
                    players=[
                        PlayerRecord(
                            id=player.id,
                            club_id=club.id,
                            position=j,
                            name=player.name,
                            details=player.model_dump(mode="json", exclude={"id", "name"}),
                        )
                        for j, player in enumerate(club.squad)
                    ],
                )
                for i, club in enumerate(league.clubs)
            ],
        )
    )


def get_league(session: Session, league_id: str) -> League | None:
    record = session.scalar(
        select(LeagueRecord)
        .where(LeagueRecord.id == league_id)
        .options(selectinload(LeagueRecord.clubs).selectinload(ClubRecord.players))
    )
    if record is None:
        return None
    league = League(
        id=record.id,
        name=record.name,
        season=record.season,
        clubs=[
            Club(
                id=club.id,
                name=club.name,
                **club.details,
                squad=[Player(id=p.id, name=p.name, **p.details) for p in club.players],
            )
            for club in record.clubs
        ],
    )
    if record.has_history:
        stored = session.scalars(
            select(FixtureRecord)
            .where(FixtureRecord.league_id == league_id)
            .order_by(FixtureRecord.position)
        ).all()
        league.fixtures = [
            Fixture(
                id=f.id,
                matchday=f.matchday,
                home_club_id=f.home_club_id,
                away_club_id=f.away_club_id,
                home_goals=f.home_goals,
                away_goals=f.away_goals,
                **f.details,
            )
            for f in stored
        ]
        league.standings = build_standings(league.clubs, league.fixtures)
        league.head_to_head = build_head_to_head(league.clubs, league.fixtures)
        validate_history(league)
    return league
