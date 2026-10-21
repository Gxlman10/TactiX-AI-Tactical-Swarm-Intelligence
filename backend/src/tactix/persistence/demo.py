"""Run with: uv run python -m tactix.persistence.demo (after migrations)."""

from tactix.domain.universe import Club, League, Player
from tactix.persistence.database import build_engine, session_factory
from tactix.persistence.leagues import add_league, get_league


def main() -> None:
    league = League(
        id="persistence-demo-league",
        name="Persistence Demo",
        season="2026",
        clubs=[
            Club(
                id="persistence-demo-club",
                name="Ashford Demo",
                squad=[
                    Player(
                        id="persistence-demo-player",
                        name="Demo Striker",
                        number=9,
                        positions=["ST"],
                    )
                ],
            )
        ],
    )
    engine = build_engine()
    sessions = session_factory(engine)
    try:
        with sessions.begin() as session:
            if get_league(session, league.id) is None:
                add_league(session, league)
        with sessions() as session:
            restored = get_league(session, league.id)
            if restored != league:
                raise RuntimeError("Stored demo roster differs from the expected league")
            print(restored.model_dump_json(indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
