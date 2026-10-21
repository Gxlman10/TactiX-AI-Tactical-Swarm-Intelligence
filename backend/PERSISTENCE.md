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

`leagues` owns `clubs`; `clubs` owns `players`. Foreign keys enforce ownership.
IDs are globally unique within each table. Position columns preserve list order.
Positions must be nonnegative and unique within their parent collection. Direct
SQL deletion of a parent with children is rejected; ORM aggregate deletion uses
the explicitly configured delete-orphan cascade.
Nested attributes, tactical identity, tendencies and player state use JSON.
Names and ownership keys have dedicated relational columns.

`add_league(session, league)` inserts a new roster. The caller controls commit
and rollback; existing IDs raise an integrity error. `get_league` reconstructs
the Pydantic contract, returning `None` for an unknown ID. This delivery supports
roster insertion and retrieval. History, events and updates require later work.
Nonempty history is rejected instead of silently discarded.

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
This query-count check does not measure latency or concurrent load. GitHub Actions
provides PostgreSQL 16 and the test URL so integration tests run in CI.
Without the test URL, PostgreSQL integration tests are skipped.

To create future migrations, use `uv run alembic revision --autogenerate -m
"Describe change"`, review the generated file, then apply it with `upgrade head`.
`uv run alembic downgrade -1` reverts the latest migration and deletes the tables
and data it created; use it only when that data can be discarded.
