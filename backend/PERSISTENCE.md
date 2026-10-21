# League persistence

From the repository root, copy `.env.example` to `.env` if needed, then run:

```sh
docker compose up -d db
```

From `backend/`:

```sh
uv sync --locked
uv run alembic upgrade head
uv run python -m tactix.persistence.demo
uv run alembic check
```

The demo commits a synthetic league, club and player, then reads them in a new
session and checks equality. Repeated runs reuse the same demo IDs.

Configuration reads the repository-root `.env`, then a working-directory `.env`.
Environment variables take precedence. If port 5432 is occupied, set these in
the repository-root `.env` before starting Docker:

```dotenv
TACTIX_POSTGRES_PORT=5433
TACTIX_DATABASE_URL=postgresql+psycopg://tactix:tactix@localhost:5433/tactix
```

The containerized backend uses the internal service address `db:5432`.

## Data model

`leagues` owns `clubs` and historical `fixtures`; `clubs` owns `players`.
Composite foreign keys prevent fixture clubs from belonging to another league.
IDs are globally unique within each table. Position columns preserve list order.
Positions must be nonnegative and unique within their parent collection. Direct
SQL deletion of a parent with children is rejected; ORM aggregate deletion uses
the explicitly configured delete-orphan cascade.
Nested attributes, tactical identity, tendencies and player state use JSON.
Names and ownership keys have dedicated relational columns.

`add_league(session, league)` inserts a roster with optional history. The caller controls commit
and rollback; existing IDs raise an integrity error. `get_league` reconstructs
the Pydantic contract, returning `None` for an unknown ID. Invalid scorer references
and summaries that disagree with fixtures are rejected before insertion.
Standings and head-to-head summaries are rebuilt from fixtures when reading,
preventing divergent stored aggregates. Scorer metadata remains in JSON with
application-level membership validation. The database enforces fixture ownership,
nonnegative scores and ordering; cross-home/away appearance conflicts within a
matchday are validated by the application. Events and updates require later work.

## PostgreSQL tests

Set `TACTIX_TEST_DATABASE_URL` to a development PostgreSQL database, then run
`uv run pytest -q`. In PowerShell:

```powershell
$env:TACTIX_TEST_DATABASE_URL = 'postgresql+psycopg://tactix:tactix@localhost:5433/tactix'
uv run pytest -q
```

Integration tests create and remove a unique schema. They verify migrations in
both directions, roster equality, foreign keys, duplicate IDs and rollback.
They also verify atomic failure partway through a roster, invalid list positions,
restricted parent deletion, and a 10-club, 230-player league read in three queries.
With history, the complete aggregate reads in four queries. Tests also cover
historical ownership, aggregate deletion and migration preservation of old rosters.
This query-count check does not measure latency or concurrent load. GitHub Actions
provides PostgreSQL 16 and the test URL so integration tests run in CI.
Without the test URL, PostgreSQL integration tests are skipped.

To create future migrations, use `uv run alembic revision --autogenerate -m
"Describe change"`, review the generated file, then apply it with `upgrade head`.
`uv run alembic downgrade -1` reverts the latest migration and deletes the tables
and data it created; use it only when that data can be discarded.
