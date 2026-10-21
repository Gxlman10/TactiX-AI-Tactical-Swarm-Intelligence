"""Relational ownership with JSON for nested domain attributes."""

from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class LeagueRecord(Base):
    __tablename__ = "leagues"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    season: Mapped[str] = mapped_column(String)
    clubs: Mapped[list["ClubRecord"]] = relationship(
        cascade="all, delete-orphan", order_by="ClubRecord.position"
    )


class ClubRecord(Base):
    __tablename__ = "clubs"
    __table_args__ = (
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
