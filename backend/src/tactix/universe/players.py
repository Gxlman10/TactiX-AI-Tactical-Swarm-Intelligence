"""Synthetic squad profiles and attribute-derived tendencies; no match results."""

import hashlib
import random
from typing import TypeVar
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel

from tactix.domain.enums import BuildUpStyle, Foot, Position
from tactix.domain.universe import (
    Club,
    GoalkeepingAttributes,
    MentalAttributes,
    PhysicalAttributes,
    Player,
    PlayerState,
    PlayerTendencies,
    TacticalIdentity,
    TechnicalAttributes,
)

# The order is the starting XI, then reserves. Roles remain within domain.Position.
FORMATIONS: dict[str, tuple[Position, ...]] = {
    "4-3-3": (
        Position.GK,
        Position.RB,
        Position.RCB,
        Position.LCB,
        Position.LB,
        Position.CDM,
        Position.CM,
        Position.CM,
        Position.RW,
        Position.ST,
        Position.LW,
    ),
    "4-2-3-1": (
        Position.GK,
        Position.RB,
        Position.RCB,
        Position.LCB,
        Position.LB,
        Position.CDM,
        Position.CDM,
        Position.RW,
        Position.CAM,
        Position.LW,
        Position.ST,
    ),
    "3-4-3": (
        Position.GK,
        Position.RCB,
        Position.CB,
        Position.LCB,
        Position.RWB,
        Position.CM,
        Position.CM,
        Position.LWB,
        Position.RW,
        Position.ST,
        Position.LW,
    ),
    "4-1-4-1": (
        Position.GK,
        Position.RB,
        Position.RCB,
        Position.LCB,
        Position.LB,
        Position.CDM,
        Position.RM,
        Position.CM,
        Position.CM,
        Position.LM,
        Position.ST,
    ),
    "5-4-1": (
        Position.GK,
        Position.RWB,
        Position.RCB,
        Position.CB,
        Position.LCB,
        Position.LWB,
        Position.RM,
        Position.CM,
        Position.CM,
        Position.LM,
        Position.ST,
    ),
    "4-4-2": (
        Position.GK,
        Position.RB,
        Position.RCB,
        Position.LCB,
        Position.LB,
        Position.RM,
        Position.CM,
        Position.CM,
        Position.LM,
        Position.ST,
        Position.ST,
    ),
    "4-3-2-1": (
        Position.GK,
        Position.RB,
        Position.RCB,
        Position.LCB,
        Position.LB,
        Position.CDM,
        Position.CM,
        Position.CM,
        Position.CAM,
        Position.CAM,
        Position.ST,
    ),
    "3-5-2": (
        Position.GK,
        Position.RCB,
        Position.CB,
        Position.LCB,
        Position.RWB,
        Position.CDM,
        Position.CM,
        Position.CM,
        Position.LWB,
        Position.ST,
        Position.ST,
    ),
    "4-2-4": (
        Position.GK,
        Position.RB,
        Position.RCB,
        Position.LCB,
        Position.LB,
        Position.CM,
        Position.CM,
        Position.RW,
        Position.ST,
        Position.ST,
        Position.LW,
    ),
    "4-5-1": (
        Position.GK,
        Position.RB,
        Position.RCB,
        Position.LCB,
        Position.LB,
        Position.RM,
        Position.CDM,
        Position.CM,
        Position.CM,
        Position.LM,
        Position.ST,
    ),
}
RESERVES = (
    Position.GK,
    Position.GK,
    Position.RB,
    Position.LB,
    Position.CB,
    Position.CB,
    Position.CDM,
    Position.CM,
    Position.CAM,
    Position.LW,
    Position.ST,
    Position.ST,
)

# Original name components, combined without reference to real player datasets.
FIRST_NAMES = (
    "Alden",
    "Bram",
    "Callen",
    "Darian",
    "Evan",
    "Finn",
    "Galen",
    "Harlan",
    "Iven",
    "Jory",
    "Kellan",
    "Loren",
    "Merrin",
    "Niall",
    "Orin",
    "Perrin",
)
LAST_NAMES = (
    "Vale",
    "Marden",
    "Corven",
    "Drell",
    "Ember",
    "Fenwick",
    "Garrow",
    "Hollow",
    "Iverley",
    "Jarrow",
    "Kestrel",
    "Loxley",
    "Mossden",
    "Nerrow",
    "Oaklen",
    "Pell",
)

# Base ratings in the order declared by each domain attribute family. Variation
# adds a shared player quality offset plus bounded per-attribute noise.
ROLE_RATINGS = {
    "keeper": (
        (43, 45, 57, 69, 73),
        (45, 51, 30, 47, 23, 18, 20, 28),
        (70, 49, 69, 65, 44, 56, 25),
    ),
    "centre_back": (
        (51, 48, 63, 80, 79),
        (55, 58, 35, 48, 32, 29, 31, 37),
        (79, 47, 62, 67, 70, 68, 81),
    ),
    "full_back": (
        (76, 74, 77, 58, 54),
        (62, 55, 60, 59, 73, 34, 42, 42),
        (66, 55, 55, 60, 61, 75, 64),
    ),
    "wing_back": (
        (78, 77, 83, 56, 49),
        (65, 57, 67, 62, 79, 43, 46, 46),
        (59, 61, 54, 57, 58, 81, 53),
    ),
    "holding": (
        (52, 51, 76, 72, 57),
        (72, 71, 48, 65, 40, 35, 52, 46),
        (79, 69, 71, 76, 69, 77, 75),
    ),
    "central": (
        (61, 61, 78, 57, 46),
        (79, 73, 65, 75, 54, 49, 65, 57),
        (63, 78, 72, 75, 51, 73, 51),
    ),
    "creator": (
        (66, 72, 60, 43, 39),
        (81, 65, 80, 84, 59, 64, 72, 69),
        (63, 85, 78, 78, 38, 54, 31),
    ),
    "wide": ((85, 86, 68, 42, 40), (62, 48, 84, 74, 77, 65, 57, 51), (59, 65, 63, 57, 39, 60, 31)),
    "striker": (
        (74, 73, 62, 73, 78),
        (48, 37, 65, 68, 35, 85, 62, 52),
        (84, 49, 78, 64, 57, 56, 26),
    ),
}


def role_for(position: Position) -> str:
    if position == Position.GK:
        return "keeper"
    if position in (Position.CB, Position.RCB, Position.LCB):
        return "centre_back"
    if position in (Position.RB, Position.LB):
        return "full_back"
    if position in (Position.RWB, Position.LWB):
        return "wing_back"
    if position == Position.CDM:
        return "holding"
    if position == Position.CM:
        return "central"
    if position == Position.CAM:
        return "creator"
    if position in (Position.RW, Position.LW, Position.RM, Position.LM):
        return "wide"
    return "striker"


def positions_for(primary: Position) -> list[Position]:
    alternatives = {
        Position.RB: Position.RWB,
        Position.RWB: Position.RB,
        Position.LB: Position.LWB,
        Position.LWB: Position.LB,
        Position.RCB: Position.CB,
        Position.LCB: Position.CB,
        Position.CDM: Position.CM,
        Position.CAM: Position.CM,
        Position.RW: Position.RM,
        Position.RM: Position.RW,
        Position.LW: Position.LM,
        Position.LM: Position.LW,
        Position.ST: Position.CF,
        Position.CF: Position.ST,
    }
    secondary = alternatives.get(primary)
    return [primary, secondary] if secondary else [primary]


def tactical_adjustments(identity: TacticalIdentity) -> dict[str, int]:
    """Transparent rating modifiers applied before clipping to 20–95."""
    modifiers = {
        "stamina": round((identity.press_intensity - 50) / 6),
        "work_rate": round((identity.press_intensity - 50) / 6),
        "pace": round((identity.defensive_line_height - 50) / 10),
        "acceleration": round((identity.tempo - 50) / 10),
        "crossing": round((identity.width - 50) / 8),
        "set_pieces": round((identity.set_piece_strength - 50) / 6),
    }
    if identity.build_up == BuildUpStyle.SHORT:
        modifiers.update(passing=6, first_touch=4, decisions=3)
    elif identity.build_up == BuildUpStyle.DIRECT:
        modifiers.update(long_passing=6, strength=3, jumping=3)
    return modifiers


def derive_tendencies(player: Player) -> PlayerTendencies:
    """Translate positional zones and measured design attributes into priors."""
    if not player.positions:
        raise ValueError("A primary position is required to derive tendencies")
    primary = player.positions[0]
    if primary == Position.GK:
        zones = ["own_penalty_area"]
    elif primary in (Position.LB, Position.LWB, Position.LW, Position.LM):
        zones = ["left_channel"]
    elif primary in (Position.RB, Position.RWB, Position.RW, Position.RM):
        zones = ["right_channel"]
    elif primary in (Position.ST, Position.CF):
        zones = ["central_penalty_area"]
    elif primary in (Position.CB, Position.LCB, Position.RCB):
        zones = ["central_defensive_third"]
    else:
        zones = ["central_midfield"]

    # Each phrase has an explicit numeric cause; never claim historical success.
    traits = {
        "passing": (player.technical.passing, "Short combinations", "Short-pass execution"),
        "long_passing": (
            player.technical.long_passing,
            "Long forward passes",
            "Long-pass execution",
        ),
        "dribbling": (
            player.technical.dribbling,
            "Ball carries and take-ons",
            "Dribbling in tight spaces",
        ),
        "crossing": (player.technical.crossing, "Crosses from wide areas", "Cross delivery"),
        "finishing": (player.technical.finishing, "Shots inside the area", "Finishing execution"),
        "marking": (player.mental.marking, "Close defensive marking", "Defensive marking"),
        "pace": (player.physical.pace, "Runs into space", "Recovery speed"),
        "composure": (
            player.mental.composure,
            "Retaining the ball under pressure",
            "Composure under pressure",
        ),
    }
    relevant = {
        "centre_back": ("marking", "pace", "composure", "passing", "long_passing"),
        "full_back": ("marking", "pace", "crossing", "passing", "composure"),
        "wing_back": ("pace", "crossing", "dribbling", "marking", "composure"),
        "holding": ("passing", "long_passing", "marking", "composure", "pace"),
        "central": ("passing", "long_passing", "dribbling", "composure", "marking"),
        "creator": ("passing", "dribbling", "composure", "finishing", "pace"),
        "wide": ("dribbling", "crossing", "finishing", "pace", "composure"),
        "striker": ("finishing", "pace", "dribbling", "composure", "passing"),
    }
    if primary == Position.GK and player.goalkeeping is None:
        raise ValueError("Goalkeeping attributes are required for goalkeeper tendencies")
    candidates = (
        [traits[key] for key in relevant[role_for(primary)]] if primary != Position.GK else []
    )
    if player.goalkeeping:
        keeper = player.goalkeeping
        candidates = [
            (keeper.reflexes, "Reaction saves", "Reaction saves"),
            (keeper.handling, "Holding shots", "Shot handling"),
            (keeper.aerial, "Claiming high balls", "High-ball claims"),
            (keeper.distribution, "Starting attacks from goal", "Goalkeeper distribution"),
            (keeper.sweeping, "Sweeping behind the defensive line", "Sweeper coverage"),
        ]
    strongest = sorted(candidates, key=lambda entry: -entry[0])[:2]
    weakest = sorted(candidates, key=lambda entry: entry[0])[:2]
    return PlayerTendencies(
        hot_zones=zones,
        favoured_actions=[
            f"{action} (design rating {rating}/100)" for rating, action, _ in strongest
        ],
        exploitable_weaknesses=[
            f"{weakness}: relative limitation (design rating {rating}/100)"
            for rating, _, weakness in weakest
        ],
    )


AttributeFamily = TypeVar("AttributeFamily", bound=BaseModel)


def _family(  # noqa: UP047 - Preserve the project's Python 3.11 compatibility.
    model: type[AttributeFamily],
    bases: tuple[int, ...],
    rng: random.Random,
    quality: int,
    modifiers: dict[str, int],
) -> AttributeFamily:
    return model(
        **{
            key: max(20, min(95, value + quality + rng.randint(-6, 6) + modifiers.get(key, 0)))
            for key, value in zip(model.model_fields, bases, strict=True)
        }
    )


def generate_squad(club: Club, seed: int) -> list[Player]:
    """Return 23 new players without mutating the club or global random state."""
    if type(seed) is not int or not 0 <= seed <= 2**63 - 1:
        raise ValueError("seed must be an integer between 0 and 2^63-1")
    if club.tactical_identity.formation not in FORMATIONS:
        raise ValueError(f"Unsupported formation: {club.tactical_identity.formation}")
    namespace = uuid5(NAMESPACE_URL, f"tactix:squad-v1:{club.id}:{seed}")
    name_rng = random.Random(int.from_bytes(hashlib.sha256(str(namespace).encode()).digest()))
    names = name_rng.sample([f"{a} {b}" for a in FIRST_NAMES for b in LAST_NAMES], 23)
    positions = FORMATIONS[club.tactical_identity.formation] + RESERVES
    modifiers = tactical_adjustments(club.tactical_identity)
    players = []
    for index, position in enumerate(positions):
        player_id = uuid5(namespace, str(index))
        rng = random.Random(int.from_bytes(hashlib.sha256(str(player_id).encode()).digest()))
        quality = rng.randint(-7, 7)
        role = role_for(position)
        physical, technical, mental = ROLE_RATINGS[role]

        left_side = position in (Position.LB, Position.LWB, Position.LW, Position.LM, Position.LCB)
        foot = Foot.LEFT if rng.random() < (0.85 if left_side else 0.18) else Foot.RIGHT
        height = (
            rng.randint(183, 202) if role in ("keeper", "centre_back") else rng.randint(165, 194)
        )
        keeper = None
        if position == Position.GK:
            sweeping = round((club.tactical_identity.defensive_line_height - 50) / 6)
            distribution = 6 if club.tactical_identity.build_up == BuildUpStyle.SHORT else 0
            keeper = GoalkeepingAttributes(
                **{
                    key: max(20, min(95, 70 + quality + rng.randint(-9, 9) + adjustment))
                    for key, adjustment in {
                        "reflexes": 3,
                        "handling": 0,
                        "aerial": 0,
                        "distribution": distribution,
                        "sweeping": sweeping,
                    }.items()
                }
            )
        player = Player(
            id=str(player_id),
            name=names[index],
            number=index + 1,
            positions=positions_for(position),
            preferred_foot=foot,
            weak_foot=rng.randint(1, 5),
            height_cm=height,
            age=rng.randint(18, 35),
            physical=_family(PhysicalAttributes, physical, rng, quality, modifiers),
            technical=_family(TechnicalAttributes, technical, rng, quality, modifiers),
            mental=_family(MentalAttributes, mental, rng, quality, modifiers),
            goalkeeping=keeper,
            state=PlayerState(morale=rng.randint(50, 80)),
        )
        # Keep the named fictional scorer available; historical/demo patterns are
        # still generated by their own tasks, never asserted by this profile.
        if club.name == "Northbridge" and position == Position.ST and index < 11:
            player.name = "Finn Hartley"
        player.tendencies = derive_tendencies(player)
        players.append(player)
    return players
