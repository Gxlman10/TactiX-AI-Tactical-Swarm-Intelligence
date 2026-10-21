"""Tactical diversity, determinism and command-line contract checks."""

import json
import random
import re
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from tactix.domain.enums import BuildUpStyle
from tactix.domain.universe import League
from tactix.universe.generator import LeagueConfig, describe_tactics, generate_league
from tactix.universe.profiles import PROFILES


@pytest.mark.parametrize("count", [8, 9, 10])
def test_club_contract_and_diversity(count):
    league = generate_league(LeagueConfig(club_count=count, generator_version="league-v1"))
    assert len(league.clubs) == count
    assert len({club.id for club in league.clubs}) == count
    assert len({club.name for club in league.clubs}) == count
    assert {"Ashford", "Northbridge"} <= {club.name for club in league.clubs}
    assert {club.tactical_identity.build_up for club in league.clubs} == set(BuildUpStyle)
    assert len({club.tactical_identity.formation for club in league.clubs}) >= 7
    for club in league.clubs:
        assert club.city and club.nickname and club.tactical_identity.philosophy
        assert club.primary_color != club.secondary_color
        assert re.fullmatch(r"#[0-9A-F]{6}", club.primary_color)
        assert re.fullmatch(r"#[0-9A-F]{6}", club.secondary_color)
        assert sum(int(n) for n in club.tactical_identity.formation.split("-")) == 10
        assert club.strengths and club.weaknesses
        assert club.squad == []
    assert not league.fixtures and not league.standings and not league.head_to_head
    assert League.model_validate_json(league.model_dump_json()) == league


def test_seed_is_reproducible_and_does_not_touch_global_random():
    before = random.getstate()
    first = generate_league(LeagueConfig(seed=123))
    assert first.model_dump_json() == generate_league(LeagueConfig(seed=123)).model_dump_json()
    assert random.getstate() == before
    second = generate_league(LeagueConfig(seed=124))
    assert first.id != second.id
    assert {club.id for club in first.clubs}.isdisjoint(club.id for club in second.clubs)
    assert first.clubs[0].tactical_identity != second.clubs[0].tactical_identity
    assert [club.name for club in first.clubs] == [club.name for club in second.clubs]
    first.clubs[0].strengths.clear()
    assert generate_league(LeagueConfig(seed=123)).clubs[0].strengths


def test_configuration_namespaces_ids_without_changing_shared_styles():
    small = generate_league(LeagueConfig(club_count=8))
    large = generate_league(LeagueConfig(club_count=10))
    assert small.id != large.id
    assert [c.tactical_identity for c in small.clubs] == [
        c.tactical_identity for c in large.clubs[:8]
    ]
    later = generate_league(LeagueConfig(season="2027/28"))
    assert later.id != large.id
    assert {c.id for c in later.clubs}.isdisjoint(c.id for c in large.clubs)


@pytest.mark.parametrize("seed", [0, 1, 42, 2026, 2**63 - 1])
def test_rating_variation_preserves_profile_and_description(seed):
    league = generate_league(LeagueConfig(seed=seed))
    for club, profile in zip(league.clubs, PROFILES, strict=True):
        identity = club.tactical_identity
        values = (
            identity.defensive_line_height,
            identity.press_intensity,
            identity.tempo,
            identity.width,
            identity.set_piece_strength,
        )
        assert all(
            abs(value - base) <= 4 for value, base in zip(values, profile.ratings, strict=True)
        )
        assert all(0 <= value <= 100 for value in values)
        assert (club.strengths, club.weaknesses) == describe_tactics(identity)
    ashford, northbridge = league.clubs[:2]
    assert ashford.tactical_identity.press_intensity >= 70
    assert ashford.tactical_identity.defensive_line_height >= 70
    assert northbridge.tactical_identity.build_up == BuildUpStyle.DIRECT
    assert northbridge.tactical_identity.defensive_line_height <= 40
    bastion = league.clubs[4]
    assert bastion.tactical_identity.defensive_line_height < 30
    assert bastion.tactical_identity.set_piece_strength > 80


@pytest.mark.parametrize(
    "kwargs",
    [
        {"club_count": 7},
        {"club_count": 11},
        {"club_count": True},
        {"seed": -1},
        {"seed": 1.5},
        {"seed": True},
        {"seed": 2**63},
        {"season": "   "},
        {"generator_version": "league-v4"},
        {"unknown": 42},
    ],
)
def test_invalid_configuration_is_rejected(kwargs):
    with pytest.raises(ValidationError):
        LeagueConfig(**kwargs)


def test_manifest_and_cli_export(tmp_path):
    root = Path(__file__).resolve().parents[3]
    manifest = root / "data/scenarios/league-base.json"
    config = LeagueConfig.model_validate_json(manifest.read_text(encoding="utf-8"))
    output = tmp_path / "league.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tactix.universe",
            "--config",
            str(manifest),
            "--clubs",
            "8",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == ""
    generated = League.model_validate_json(output.read_text(encoding="utf-8"))
    assert generated == generate_league(
        LeagueConfig(seed=config.seed, club_count=8, generator_version=config.generator_version)
    )
    failed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tactix.universe",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert failed.returncode == 2
    assert League.model_validate_json(output.read_text(encoding="utf-8")) == generated


def test_cli_stdout_and_invalid_input():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tactix.universe",
            "--seed",
            "19",
            "--clubs",
            "9",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert len(json.loads(result.stdout)["clubs"]) == 9
    failed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tactix.universe",
            "--clubs",
            "4",
        ],
        capture_output=True,
        text=True,
    )
    assert failed.returncode == 2
    assert failed.stdout == ""
