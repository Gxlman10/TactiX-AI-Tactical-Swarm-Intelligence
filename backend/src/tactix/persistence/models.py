"""Relational ownership with JSON for nested domain attributes."""

from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class LeagueRecord(Base):
    __tablename__ = "leagues"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    season: Mapped[str] = mapped_column(String)
    has_history: Mapped[bool] = mapped_column(Boolean, server_default="false")
    clubs: Mapped[list["ClubRecord"]] = relationship(
        cascade="all, delete-orphan", order_by="ClubRecord.position"
    )
    fixtures: Mapped[list["FixtureRecord"]] = relationship(
        cascade="all, delete-orphan", order_by="FixtureRecord.position"
    )


class ClubRecord(Base):
    __tablename__ = "clubs"
    __table_args__ = (
        UniqueConstraint("league_id", "id", name="uq_clubs_league_id_id"),
        UniqueConstraint("league_id", "position"),
        CheckConstraint("position >= 0", name="ck_clubs_position_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    league_id: Mapped[str] = mapped_column(ForeignKey("leagues.id"), index=True)
    position: Mapped[int]
    name: Mapped[str] = mapped_column(String)
    details: Mapped[dict[str, Any]] = mapped_column(JSON)
    players: Mapped[list["PlayerRecord"]] = relationship(
        cascade="all, delete-orphan", order_by="PlayerRecord.position"
    )


class PlayerRecord(Base):
    __tablename__ = "players"
    __table_args__ = (
        UniqueConstraint("club_id", "position"),
        CheckConstraint("position >= 0", name="ck_players_position_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    club_id: Mapped[str] = mapped_column(ForeignKey("clubs.id"), index=True)
    position: Mapped[int]
    name: Mapped[str] = mapped_column(String)
    details: Mapped[dict[str, Any]] = mapped_column(JSON)


class FixtureRecord(Base):
    __tablename__ = "fixtures"
    __table_args__ = (
        ForeignKeyConstraint(
            ["league_id", "home_club_id"],
            ["clubs.league_id", "clubs.id"],
            name="fk_fixtures_home_club",
        ),
        ForeignKeyConstraint(
            ["league_id", "away_club_id"],
            ["clubs.league_id", "clubs.id"],
            name="fk_fixtures_away_club",
        ),
        UniqueConstraint("league_id", "position"),
        UniqueConstraint("league_id", "matchday", "home_club_id"),
        UniqueConstraint("league_id", "matchday", "away_club_id"),
        CheckConstraint("home_club_id <> away_club_id", name="ck_fixtures_distinct_clubs"),
        CheckConstraint("home_goals >= 0 AND away_goals >= 0", name="ck_fixtures_goals"),
        CheckConstraint("matchday >= 1 AND position >= 0", name="ck_fixtures_order"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    league_id: Mapped[str] = mapped_column(ForeignKey("leagues.id"), index=True)
    position: Mapped[int]
    matchday: Mapped[int]
    home_club_id: Mapped[str] = mapped_column(String, index=True)
    away_club_id: Mapped[str] = mapped_column(String, index=True)
    home_goals: Mapped[int]
    away_goals: Mapped[int]
    details: Mapped[dict[str, Any]] = mapped_column(JSON)
