"""Original bounded design rules, not calibrated football prediction models."""

import math

from tactix.domain.common import Point
from tactix.domain.enums import EventType
from tactix.domain.universe import Player


def fatigue(player: Player, minute: float) -> float:
    return min(100.0, player.state.fatigue + max(0, minute) / 90 * (100 - player.physical.stamina))


def distance(start: Point, end: Point) -> float:
    """Metres on a 105 by 68 metre pitch from normalized input coordinates."""
    return math.hypot((end.x - start.x) * 1.05, (end.y - start.y) * 0.68)


def direction(start: Point, end: Point) -> float:
    # Keep authored recordings byte-stable across Python/libm implementations.
    return round(math.atan2((end.y - start.y) * 0.68, (end.x - start.x) * 1.05), 15)


def shot_angle(point: Point) -> float:
    dx, dy = (100 - point.x) * 1.05, (50 - point.y) * 0.68
    return abs(math.atan2(dy + 3.66, dx) - math.atan2(dy - 3.66, dx))


def shot_value(point: Point) -> float:
    metres = distance(point, Point(x=100, y=50))
    return round(
        max(
            0.01,
            min(0.6, 0.03 + 0.4 * shot_angle(point) / math.pi + 0.12 * max(0, 1 - metres / 35)),
        ),
        4,
    )


def action_probability(
    player: Player,
    kind: EventType,
    metres: float,
    minute: float,
    pressured: bool,
) -> float:
    skill = player.technical.passing if metres < 25 else player.technical.long_passing
    if kind == EventType.CARRY:
        skill = (player.technical.first_touch + player.physical.pace) / 2
    elif kind == EventType.DRIBBLE:
        skill = (player.technical.dribbling + player.physical.acceleration) / 2
    probability = (
        0.57
        + skill / 260
        + player.mental.decisions / 1400
        - metres / 900
        - fatigue(player, minute) / 350
        - (0.08 + (100 - player.mental.composure) / 600 if pressured else 0)
    )
    return max(0.15, min(0.96, probability))


def pitch_zone(point: Point) -> int:
    return min(int(point.x / (100 / 3)), 2) * 6 + min(int(point.y / (100 / 6)), 5) + 1


def mirror(point: Point) -> Point:
    return Point(x=100 - point.x, y=100 - point.y)
