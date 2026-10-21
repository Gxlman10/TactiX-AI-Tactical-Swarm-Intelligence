"""Reproducible fictional clubs against the frozen League contract."""

import hashlib
import random
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tactix.domain.enums import BuildUpStyle
from tactix.domain.universe import Club, League, TacticalIdentity
from tactix.universe.history import generate_history
from tactix.universe.players import generate_squad
from tactix.universe.profiles import PROFILES


class LeagueConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    generator_version: Literal["league-v1", "league-v2", "league-v3"] = "league-v3"
    seed: int = Field(default=42, ge=0, le=2**63 - 1)
    club_count: int = Field(default=10, ge=8, le=10)
    season: str = "2026/27"
    history_matchdays: int = Field(default=12, ge=12, le=14)

    @field_validator("season")
    @classmethod
    def validate_season(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("season must not be blank")
        return value

    @model_validator(mode="after")
    def validate_history_version(self) -> "LeagueConfig":
        if self.generator_version != "league-v3" and self.history_matchdays != 12:
            raise ValueError("Custom history_matchdays requires league-v3")
        return self


def describe_tactics(identity: TacticalIdentity) -> tuple[list[str], list[str]]:
    """Design expectations from ratings, not claims about observed match results."""
    strengths, weaknesses = [], []
    if identity.build_up == BuildUpStyle.SHORT:
        strengths.append("Short-passing support in build-up")
        weaknesses.append("Short build-up can be targeted by a coordinated press")
    elif identity.build_up == BuildUpStyle.DIRECT:
        strengths.append("Early forward progression without prolonged build-up")
        weaknesses.append("Direct progression depends on winning first and second balls")
    else:
        strengths.append("Multiple build-up routes available")
        weaknesses.append("Switching build-up routes requires coordinated movement")
    if identity.defensive_line_height >= 70:
        strengths.append("High defensive line compresses space around midfield")
        weaknesses.append("Space behind the high defensive line")
    elif identity.defensive_line_height <= 40:
        strengths.append("Deep defensive cover near the penalty area")
        weaknesses.append("Deep starting positions concede territory")
    if identity.press_intensity >= 70:
        strengths.append("Aggressive pressure designed to force early turnovers")
        weaknesses.append("Sustained pressing places high demands on stamina")
    elif identity.press_intensity <= 40:
        weaknesses.append("Low pressure allows opponents time to circulate possession")
    if identity.width >= 70:
        strengths.append("Wide outlets stretch the opposing defensive block")
        weaknesses.append("Wide spacing can leave gaps between supporting players")
    elif identity.width <= 40:
        strengths.append("Narrow spacing supports central combinations")
        weaknesses.append("Limited natural width against compact central blocks")
    if identity.tempo >= 75:
        strengths.append("Fast tempo targets unsettled defensive shapes")
        weaknesses.append("Fast execution increases technical demands under pressure")
    elif identity.tempo <= 45:
        strengths.append("Patient circulation supports controlled possession")
        weaknesses.append("Slow circulation allows defensive blocks to reset")
    if identity.set_piece_strength >= 70:
        strengths.append("Strong designed emphasis on set-piece execution")
    elif identity.set_piece_strength <= 50:
        weaknesses.append("Lower set-piece execution rating")
    return strengths, weaknesses


def generate_league(config: LeagueConfig | None = None) -> League:
    """Generate versioned clubs, squads (v2+) and prior fixtures (v3).

    Per-club random streams preserve tactical ratings when expanding the same
    seed and season to nine or ten clubs. IDs namespace each configuration,
    preventing collisions when multiple generated leagues share one database.
    """
    config = config or LeagueConfig()
    identity_key = (
        f"tactix:{config.generator_version}:{config.seed}:{config.season}:{config.club_count}"
    )
    if config.generator_version == "league-v3":
        identity_key += f":{config.history_matchdays}"
    namespace = uuid5(NAMESPACE_URL, identity_key)
    clubs = []
    for profile in PROFILES[: config.club_count]:
        digest = hashlib.sha256(
            f"league-v1:{config.seed}:{config.season}:{profile.slug}".encode()
        ).digest()
        rng = random.Random(int.from_bytes(digest, "big"))
        line, press, tempo, width, set_pieces = (
            rating + rng.randint(-4, 4) for rating in profile.ratings
        )
        identity = TacticalIdentity(
            formation=profile.formation,
            build_up=profile.build_up,
            defensive_line_height=line,
            press_intensity=press,
            tempo=tempo,
            width=width,
            set_piece_strength=set_pieces,
            philosophy=profile.philosophy,
        )
        strengths, weaknesses = describe_tactics(identity)
        clubs.append(
            Club(
                id=str(uuid5(namespace, profile.slug)),
                name=profile.name,
                city=profile.city,
                nickname=profile.nickname,
                primary_color=profile.colors[0],
                secondary_color=profile.colors[1],
                tactical_identity=identity,
                strengths=strengths,
                weaknesses=weaknesses,
            )
        )
        if config.generator_version != "league-v1":
            clubs[-1].squad = generate_squad(clubs[-1], config.seed)
    league = League(
        id=str(namespace), name="TactiX Synthetic League", season=config.season, clubs=clubs
    )
    return (
        generate_history(league, config.seed, config.history_matchdays)
        if config.generator_version == "league-v3"
        else league
    )
