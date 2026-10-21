"""PostgreSQL integration checks, isolated in a disposable schema."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from tactix.domain.universe import Club, League, Player, StandingRow
from tactix.persistence.database import build_engine, session_factory
from tactix.persistence.leagues import add_league, get_league
from tactix.persistence.models import ClubRecord, PlayerRecord
from tactix.universe.generator import LeagueConfig, generate_league


@pytest.fixture
def database(monkeypatch):
    url = os.getenv("TACTIX_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TACTIX_TEST_DATABASE_URL to run PostgreSQL integration tests")
    admin = build_engine(url)
    schema = "test_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    monkeypatch.setenv("TACTIX_DATABASE_URL", isolated.render_as_string(hide_password=False))
    engine = build_engine()
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    try:
        command.upgrade(config, "head")
        yield engine, config
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_migration_round_trip_and_roster(database):
    engine, config = database
    sessions = session_factory(engine)
    league = League(
        id="league",
        name="Liga sintética",
        season="2026",
        clubs=[
            Club(
                id="club",
                name="Ashford",
                squad=[
                    Player(
                        id="player",
                        name="José",
                        number=9,
                        positions=["ST"],
                        technical={"finishing": 87},
                        tendencies={"hot_zones": ["box"]},
                    ),
                    Player(
                        id="keeper",
                        name="Keeper",
                        number=1,
                        positions=["GK"],
                        goalkeeping={"reflexes": 91},
                    ),
                ],
            ),
            Club(id="empty", name="Empty roster"),
        ],
    )
    with sessions.begin() as session:
        add_league(session, league)
    with sessions() as session:
        assert get_league(session, league.id) == league
        assert get_league(session, "missing") is None
    with pytest.raises(IntegrityError), sessions.begin() as session:
        add_league(session, league)
    with pytest.raises(IntegrityError), sessions.begin() as session:
        session.execute(
            text(
                "INSERT INTO clubs (id, league_id, position, name, details) "
                "VALUES ('orphan', 'missing', 0, 'Orphan', '{}')"
            )
        )
    with sessions.begin() as session:
        add_league(session, League(id="rollback", name="Rollback", season="2026"))
        session.flush()
        session.rollback()
    with sessions() as session:
        assert get_league(session, "rollback") is None
    command.check(config)
    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    command.upgrade(config, "head")
    assert {"leagues", "clubs", "players"} <= set(inspect(engine).get_table_names())


def test_history_is_not_silently_discarded():
    league = League(id="l", name="League", season="2026", standings=[StandingRow(club_id="c")])
    from unittest.mock import Mock

    session = Mock()
    with pytest.raises(ValueError, match="history"):
        add_league(session, league)
    session.add.assert_not_called()


def test_roster_failure_is_atomic(database):
    engine, _ = database
    sessions = session_factory(engine)
    original = League(
        id="original",
        name="Original",
        season="2026",
        clubs=[
            Club(
                id="original-club",
                name="Original",
                squad=[
                    Player(id="shared-id", name="Existing", number=1, positions=["GK"]),
                ],
            ),
        ],
    )
    with sessions.begin() as session:
        add_league(session, original)
    broken = League(
        id="broken",
        name="Broken",
        season="2026",
        clubs=[
            Club(
                id="new-club",
                name="New",
                squad=[
                    Player(id="new-player", name="New", number=9, positions=["ST"]),
                    Player(id="shared-id", name="Collision", number=1, positions=["GK"]),
                ],
            ),
        ],
    )
    with pytest.raises(IntegrityError), sessions.begin() as session:
        add_league(session, broken)
    with sessions() as session:
        assert get_league(session, "broken") is None
        assert session.get(ClubRecord, "new-club") is None
        assert session.get(PlayerRecord, "new-player") is None
        assert get_league(session, "original") == original


def test_full_league_uses_bounded_queries(database):
    engine, _ = database
    sessions = session_factory(engine)
    league = League(
        id="full",
        name="Full League",
        season="2026",
        clubs=[
            Club(
                id=f"club-{i}",
                name=f"Club {i}",
                squad=[
                    Player(id=f"player-{i}-{j}", name=f"Player {j}", number=j + 1, positions=["CM"])
                    for j in range(23)
                ],
            )
            for i in range(10)
        ],
    )
    with sessions.begin() as session:
        add_league(session, league)
    queries = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with sessions() as session:
            restored = get_league(session, league.id)
        assert restored == league
        assert len(queries) == 3
    finally:
        event.remove(engine, "before_cursor_execute", capture)


@pytest.mark.parametrize("position", [-1, 0])
def test_invalid_roster_order_is_rejected(database, position):
    engine, _ = database
    sessions = session_factory(engine)
    with sessions.begin() as session:
        add_league(
            session,
            League(
                id="l",
                name="League",
                season="2026",
                clubs=[
                    Club(id="c", name="Club"),
                ],
            ),
        )
    # Negative position or a second club occupying the same list position.
    with pytest.raises(IntegrityError), sessions.begin() as session:
        session.add(ClubRecord(id="bad", league_id="l", position=position, name="Bad", details={}))


def test_parent_delete_is_restricted(database):
    engine, _ = database
    sessions = session_factory(engine)
    with sessions.begin() as session:
        add_league(
            session,
            League(
                id="l",
                name="League",
                season="2026",
                clubs=[
                    Club(id="c", name="Club"),
                ],
            ),
        )
    with pytest.raises(IntegrityError), sessions.begin() as session:
        session.execute(text("DELETE FROM leagues WHERE id = 'l'"))


def test_generated_leagues_round_trip_without_id_collisions(database):
    engine, _ = database
    sessions = session_factory(engine)
    leagues = [generate_league(LeagueConfig(seed=seed)) for seed in (42, 43)]
    leagues.append(generate_league(LeagueConfig(seed=42, generator_version="league-v1")))
    assert sum(len(club.squad) for club in leagues[0].clubs) == 230
    with sessions.begin() as session:
        for league in leagues:
            add_league(session, league)
    with sessions() as session:
        for league in leagues:
            assert get_league(session, league.id) == league
