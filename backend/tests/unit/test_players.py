"""Squad coverage, attribute causality and versioned universe regression tests."""

import hashlib
import random
import subprocess
import sys
from collections import Counter

import pytest

from tactix.domain.enums import BuildUpStyle, Position
from tactix.domain.universe import Club, League, Player, TacticalIdentity
from tactix.universe.generator import LeagueConfig, generate_league
from tactix.universe.players import FORMATIONS, derive_tendencies, generate_squad


@pytest.mark.parametrize("seed", [0, 42, 2026, 2**63 - 1])
@pytest.mark.parametrize("count", [8, 9, 10])
def test_squads_cover_formations_and_preserve_player_contract(seed, count):
    league = generate_league(LeagueConfig(seed=seed, club_count=count))
    all_ids = []
    for club in league.clubs:
        assert len(club.squad) == 23
        assert len({p.name for p in club.squad}) == 23
        assert {p.number for p in club.squad} == set(range(1, 24))
        assert [p.positions[0] for p in club.squad[:11]] == list(
            FORMATIONS[club.tactical_identity.formation]
        )
        assert sum(p.positions[0] == Position.GK for p in club.squad) == 3
        for player in club.squad:
            all_ids.append(player.id)
            assert len(player.positions) == len(set(player.positions))
            assert (player.goalkeeping is not None) == (player.positions == [Position.GK])
            assert 18 <= player.age <= 35
            assert 165 <= player.height_cm <= 202
            for family in (player.physical, player.technical, player.mental, player.goalkeeping):
                if family:
                    assert all(20 <= v <= 95 for v in family.model_dump().values())
            assert player.state.fatigue == 0
            assert 50 <= player.state.morale <= 80
            assert player.state.yellow_cards_season == 0
            assert player.state.suspended is False
            assert player.tendencies.hot_zones
            assert len(player.tendencies.favoured_actions) == 2
            assert len(player.tendencies.exploitable_weaknesses) == 2
    assert len(set(all_ids)) == 23 * count
    assert League.model_validate_json(league.model_dump_json()) == league


def test_squad_determinism_and_independence():
    club = generate_league(LeagueConfig(generator_version="league-v1")).clubs[0]
    before = random.getstate()
    squad = generate_squad(club, 42)
    assert squad == generate_squad(club, 42)
    assert random.getstate() == before
    assert club.squad == []
    assert squad != generate_squad(club, 43)
    assert {p.id for p in squad}.isdisjoint(p.id for p in generate_squad(club, 43))
    squad[0].physical.pace = 0
    assert generate_squad(club, 42)[0].physical.pace != 0


def test_positions_produce_distinct_attribute_profiles():
    squad = generate_league().clubs[0].squad
    keeper, defender, pivot, winger, striker = squad[0], squad[2], squad[5], squad[8], squad[9]
    assert defender.mental.marking > winger.mental.marking
    assert defender.physical.strength > winger.physical.strength
    assert striker.technical.finishing > defender.technical.finishing
    assert pivot.technical.passing > striker.technical.passing
    assert winger.physical.pace > defender.physical.pace
    assert keeper.goalkeeping.reflexes > keeper.technical.finishing


def test_tactical_demands_change_attributes_with_same_random_draws():
    base = Club(id="controlled", name="Controlled", tactical_identity=TacticalIdentity())
    high_press = base.model_copy(deep=True)
    high_press.tactical_identity.press_intensity = 95
    original = generate_squad(base, 5)
    pressing = generate_squad(high_press, 5)
    assert all(
        p.physical.stamina > q.physical.stamina for p, q in zip(pressing, original, strict=True)
    )
    assert all(
        p.mental.work_rate > q.mental.work_rate for p, q in zip(pressing, original, strict=True)
    )
    short = base.model_copy(deep=True)
    direct = base.model_copy(deep=True)
    short.tactical_identity.build_up = BuildUpStyle.SHORT
    direct.tactical_identity.build_up = BuildUpStyle.DIRECT
    short_squad, direct_squad = generate_squad(short, 5), generate_squad(direct, 5)
    assert sum(p.technical.passing for p in short_squad) > sum(
        p.technical.passing for p in direct_squad
    )
    assert sum(p.technical.long_passing for p in direct_squad) > sum(
        p.technical.long_passing for p in short_squad
    )


def test_tendencies_explain_attributes_without_fabricating_history():
    player = Player(
        id="test",
        name="Test",
        number=9,
        positions=[Position.LW],
        technical={"dribbling": 95, "crossing": 90, "finishing": 20},
    )
    tendencies = derive_tendencies(player)
    assert tendencies.hot_zones == ["left_channel"]
    assert "Ball carries and take-ons (design rating 95/100)" in tendencies.favoured_actions
    assert any(
        "Finishing execution" in phrase and "20/100" in phrase
        for phrase in tendencies.exploitable_weaknesses
    )
    player.technical.finishing = 99
    changed = derive_tendencies(player)
    assert "Shots inside the area (design rating 99/100)" in changed.favoured_actions
    assert not any("Finishing execution" in phrase for phrase in changed.exploitable_weaknesses)


def test_v1_output_is_preserved_and_v2_keeps_club_tactics():
    v1 = generate_league(LeagueConfig(generator_version="league-v1"))
    v2 = generate_league(LeagueConfig(generator_version="league-v2"))
    assert hashlib.sha256(v2.model_dump_json().encode()).hexdigest() == (
        "2c76bcec82f9531e8c8161a6354e270b77b5190a9254661b766b81eab6d27ba5"
    )
    assert v1.id == "f4d4f1c2-b820-54a1-b7ee-7caa477d44b9"
    assert hashlib.sha256(v1.model_dump_json().encode()).hexdigest() == (
        "83ae0ed2bfcdfbbee286304d0be66078a061e26de1faed167b25ad830f41acf7"
    )
    assert all(not club.squad for club in v1.clubs)
    assert [c.tactical_identity for c in v1.clubs] == [c.tactical_identity for c in v2.clubs]
    assert {c.id for c in v1.clubs}.isdisjoint(c.id for c in v2.clubs)
    assert v1.id != v2.id
    northbridge = v2.clubs[1]
    assert Counter(p.name for p in northbridge.squad)["Finn Hartley"] == 1


@pytest.mark.parametrize("seed", [-1, True, 1.5, 2**63])
def test_invalid_seed_is_rejected(seed):
    with pytest.raises(ValueError, match="seed"):
        generate_squad(Club(id="c", name="Club"), seed)


def test_unsupported_formation_is_explicit():
    club = Club(id="c", name="Club", tactical_identity=TacticalIdentity(formation="2-2-6"))
    with pytest.raises(ValueError, match="Unsupported formation"):
        generate_squad(club, 42)


def test_striker_limitations_focus_on_attacking_role():
    player = Player(
        id="s",
        name="Striker",
        number=9,
        positions=[Position.ST],
        mental={"marking": 0},
        technical={"passing": 30, "finishing": 90},
    )
    tendencies = derive_tendencies(player)
    assert any("Short-pass execution" in text for text in tendencies.exploitable_weaknesses)
    assert not any("Defensive marking" in text for text in tendencies.exploitable_weaknesses)


def test_cli_generates_complete_squads_and_reproducible_json():
    outputs = [
        subprocess.run(
            [
                sys.executable,
                "-m",
                "tactix.universe",
                "--seed",
                "42",
                "--clubs",
                "8",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for _ in range(2)
    ]
    assert (
        hashlib.sha256(outputs[0].encode()).digest() == hashlib.sha256(outputs[1].encode()).digest()
    )
    league = League.model_validate_json(outputs[0])
    assert sum(len(c.squad) for c in league.clubs) == 184
