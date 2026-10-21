"""Authored fictional identities, never imported from real football datasets."""

from dataclasses import dataclass

from tactix.domain.enums import BuildUpStyle


@dataclass(frozen=True)
class ClubProfile:
    slug: str
    name: str
    city: str
    nickname: str
    colors: tuple[str, str]
    formation: str
    build_up: BuildUpStyle
    # Defensive line, press, tempo, width, set pieces (0–100 design ratings).
    ratings: tuple[int, int, int, int, int]
    philosophy: str


PROFILES = (
    ClubProfile(
        "ashford",
        "Ashford",
        "Ashford Vale",
        "The Embers",
        ("#9B2848", "#FFF1D6"),
        "4-3-3",
        BuildUpStyle.SHORT,
        (76, 82, 72, 68, 52),
        "Commit midfielders to short combinations and counter-press after losing possession.",
    ),
    ClubProfile(
        "northbridge",
        "Northbridge",
        "Northbridge Reach",
        "The Riveters",
        ("#244C70", "#D9C391"),
        "4-2-3-1",
        BuildUpStyle.DIRECT,
        (36, 40, 84, 73, 64),
        "Protect the centre with two holding midfielders and release runners into wide channels.",
    ),
    ClubProfile(
        "cinderwick",
        "Cinderwick Forge",
        "Cinderwick",
        "The Sparks",
        ("#C65B25", "#1F2732"),
        "3-4-3",
        BuildUpStyle.MIXED,
        (85, 89, 83, 82, 57),
        "Push wing-backs high and force early turnovers with an aggressive front three.",
    ),
    ClubProfile(
        "merehaven",
        "Merehaven Tides",
        "Merehaven",
        "The Tides",
        ("#16756D", "#E8F4F0"),
        "4-1-4-1",
        BuildUpStyle.SHORT,
        (56, 53, 35, 62, 47),
        "Recycle through a deep pivot and move the opponent before accelerating the attack.",
    ),
    ClubProfile(
        "thornmere",
        "Thornmere Bastion",
        "Thornmere",
        "The Wardens",
        ("#535B38", "#EEE5C8"),
        "5-4-1",
        BuildUpStyle.DIRECT,
        (22, 26, 57, 36, 91),
        "Defend the box in two compact lines and build attacking opportunities from set pieces.",
    ),
    ClubProfile(
        "vespergate",
        "Vespergate Arrows",
        "Vespergate",
        "The Arrows",
        ("#633E81", "#F0D7A1"),
        "4-4-2",
        BuildUpStyle.DIRECT,
        (45, 59, 88, 85, 72),
        "Find wide runners quickly and support early crosses with two centre forwards.",
    ),
    ClubProfile(
        "brackenport",
        "Brackenport Weavers",
        "Brackenport",
        "The Weavers",
        ("#245E8C", "#F4CB69"),
        "4-3-2-1",
        BuildUpStyle.SHORT,
        (65, 61, 49, 29, 51),
        "Create narrow midfield overloads and combine through two inside creators.",
    ),
    ClubProfile(
        "halewick",
        "Halewick Lanterns",
        "Halewick",
        "The Lanterns",
        ("#B38724", "#182C42"),
        "3-5-2",
        BuildUpStyle.MIXED,
        (54, 57, 59, 60, 67),
        "Keep three central defenders and adjust the wing-backs to balance attack and cover.",
    ),
    ClubProfile(
        "dunvale",
        "Dunvale Kites",
        "Dunvale",
        "The Kites",
        ("#843950", "#D6E9EA"),
        "4-2-4",
        BuildUpStyle.MIXED,
        (73, 74, 90, 91, 43),
        "Stretch the last line with four attackers and accept space around the midfield pair.",
    ),
    ClubProfile(
        "silverfen",
        "Silverfen Compass",
        "Silverfen",
        "The Navigators",
        ("#42615D", "#DCE0E8"),
        "4-5-1",
        BuildUpStyle.MIXED,
        (43, 47, 45, 48, 78),
        "Screen central progression with five midfielders and release a lone forward selectively.",
    ),
)
