"""Closed vocabularies shared across every layer. Keep these authoritative and stable."""

from __future__ import annotations

from enum import StrEnum


class Foot(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    BOTH = "both"


class Position(StrEnum):
    GK = "GK"
    RB = "RB"
    RCB = "RCB"
    CB = "CB"
    LCB = "LCB"
    LB = "LB"
    RWB = "RWB"
    LWB = "LWB"
    CDM = "CDM"
    CM = "CM"
    CAM = "CAM"
    RM = "RM"
    LM = "LM"
    RW = "RW"
    LW = "LW"
    CF = "CF"
    ST = "ST"


class BuildUpStyle(StrEnum):
    SHORT = "short"
    DIRECT = "direct"
    MIXED = "mixed"


class EventType(StrEnum):
    # In possession
    PASS = "pass"
    CARRY = "carry"
    DRIBBLE = "dribble"
    KEY_PASS = "key_pass"
    ASSIST = "assist"
    SHOT = "shot"
    GOAL = "goal"
    # Defensive
    TACKLE = "tackle"
    INTERCEPTION = "interception"
    BLOCK = "block"
    CLEARANCE = "clearance"
    RECOVERY = "recovery"
    DUEL = "duel"
    PRESS = "press"
    COUNTER_PRESS = "counter_press"
    # Goalkeeper
    SAVE = "save"
    KEEPER_SWEEP = "keeper_sweep"
    DISTRIBUTION = "distribution"
    # Set pieces / stoppages
    CORNER = "corner"
    FREE_KICK = "free_kick"
    THROW_IN = "throw_in"
    PENALTY = "penalty"
    GOAL_KICK = "goal_kick"
    KICKOFF = "kickoff"
    # Discipline / other
    FOUL = "foul"
    CARD = "card"
    OFFSIDE = "offside"
    SUBSTITUTION = "substitution"
    INJURY = "injury"


class BodyPart(StrEnum):
    LEFT_FOOT = "left_foot"
    RIGHT_FOOT = "right_foot"
    HEAD = "head"
    OTHER = "other"


class PlayPattern(StrEnum):
    OPEN_PLAY = "open_play"
    FROM_CORNER = "from_corner"
    FROM_FREE_KICK = "from_free_kick"
    FROM_THROW_IN = "from_throw_in"
    COUNTER = "counter"
    DIRECT_FREE_KICK = "direct_free_kick"
    PENALTY = "penalty"
    GOAL_KICK = "goal_kick"
    KEEPER = "keeper"


class Outcome(StrEnum):
    SUCCESS = "success"
    FAIL = "fail"


class ShotOutcome(StrEnum):
    ON_TARGET = "on_target"
    OFF_TARGET = "off_target"
    BLOCKED = "blocked"
    SAVED = "saved"
    POST = "post"
    GOAL = "goal"


class PossessionPhase(StrEnum):
    BUILD_UP = "build_up"
    PROGRESSION = "progression"
    FINAL_THIRD = "final_third"
    OUTCOME = "outcome"


class CardType(StrEnum):
    YELLOW = "yellow"
    SECOND_YELLOW = "second_yellow"
    RED = "red"


class ViewMode(StrEnum):
    ANALYST = "analyst"
    FAN = "fan"


class Language(StrEnum):
    EN = "en"
    ES = "es"


class Frame(StrEnum):
    """The lens a finding reasons through — the axis of an Analyst vs Historian disagreement."""

    TACTICAL = "tactical"
    HISTORICAL = "historical"


class AgentName(StrEnum):
    TACTICAL_ANALYST = "tactical_analyst"
    HISTORIAN = "historian"
    NARRATOR = "narrator"
    PERSONALIZER = "personalizer"
    ORCHESTRATOR = "orchestrator"
