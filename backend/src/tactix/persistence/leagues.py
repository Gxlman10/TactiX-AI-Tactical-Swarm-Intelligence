"""Save and load league rosters without changing the domain contracts."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from tactix.domain.universe import Club, League, Player
from tactix.persistence.models import ClubRecord, LeagueRecord, PlayerRecord


def add_league(session: Session, league: League) -> None:
    """Insert a roster. The caller commits; duplicate IDs raise IntegrityError.

    History belongs to a later migration and is rejected to prevent silent data loss.
    """
    if league.fixtures or league.standings or league.head_to_head:
        raise ValueError("League history persistence is not implemented yet")
    session.add(
        LeagueRecord(
            id=league.id,
            name=league.name,
            season=league.season,
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
    return League(
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
