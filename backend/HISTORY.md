# Synthetic previous fixtures

`league-v3` adds a prior context window to the generated clubs and squads.
It is the default. Reproduce the baseline from `backend/`:

```sh
uv run alembic upgrade head
uv run python -m tactix.universe --config ../data/scenarios/league-history.json
uv run python -m tactix.universe --seed 42 --clubs 9 --matchdays 14
```

Generation itself does not need PostgreSQL. The migration is required when
persisting the result. `league-v1` and `league-v2` retain their original JSON.
The old manifests still choose those versions explicitly. Custom matchday counts
on the older versions are rejected instead of being silently ignored.

## Calendar and context window

The default is twelve matchdays; twelve through fourteen are accepted. A seeded
circle schedule plays each opponent once before reversing the venues. Clubs
never play themselves or appear twice on one matchday. Nine-club leagues have
one bye per matchday, so each team has ten or eleven appearances after twelve
matchdays, and twelve or thirteen after fourteen matchdays. Even-sized leagues
play on every matchday. The resulting context contains 10–14 games per club.

For eight clubs, fourteen matchdays cover an entire double round robin. Thus
this is a prior context window, not exactly half a season for every league size.
The fixture list contains 48–70 matches depending on club and matchday counts.

## Result generation

Each fixture has an independent deterministic random stream. A side takes
7–15 synthetic shot attempts plus round((tempo − 50) / 20), with a minimum of four.
Only the starting outfield players can score; selection is weighted by finishing
squared plus ten times positioning. Shot conversion uses an original bounded
design probability:

```text
defence = mean((marking + positioning) / 2 over opposing starting outfield players)
p = clamp(uniform(0.04, 0.24)
          + (shooter.finishing - defence) / 450
          + (65 - keeper.reflexes) / 600
          + (0.015 for the home side), 0.02, 0.45)
```

A successful Bernoulli draw creates a goal and its scorer/minute. The sum of
attempt probabilities is the side's synthetic xG-like value, rounded to three
decimals. This is an uncalibrated design model, not official xG, a learned model
or a prediction of real football. Goals can be higher or lower than that sum.

Possession uses mean passing, a short-build-up bias, a home bias and bounded
noise, clamped to 30–70%. Away possession is 100 minus the stored home value.
The fixture records formations, shot totals and goal summaries. Its pattern
note describes its earliest recorded goal, or a goalless match. It does not
invent midfield turnovers, pressure chains or the planted Ashford narrative.
Goal minutes have one-minute precision; ties use stable stored order.

## Table, recent form and head-to-head

`build_standings(clubs, fixtures, venue="all")` calculates played, won, drawn,
lost, goals for/against, goal difference and points from chronological results.
Wins earn three points, draws one and losses zero. Sorting uses points, goal
difference, goals scored, then club ID for a stable exact tie. These are explicit
synthetic competition rules, not claims about any real league's rules.

Form stores the last five actual appearances, newest first. A bye adds no result.
Use `venue="home"` or `venue="away"` for splits using the same StandingRow contract;
the overall table equals the sum of those venue totals.

`build_head_to_head` returns one record per unordered club pair, retaining the
club-list orientation. Wins, draws and the latest result come from the matching
fixtures. Its tendencies state counts such as both teams scoring in x of n
meetings and total goals across n meetings. A small sample is stated explicitly;
these are descriptive counts, not predictions or unsupported causal patterns.

## Persistence, integrity and limits

Historical fixtures have their own table. Composite foreign keys enforce that
both sides belong to the fixture's league. Goals, matchday and list position
have database constraints. Scorers, minutes and richer metadata use JSON and
application-level validation against the actual squads. Duplicate appearances
across both sides of a matchday are also checked by the application.

Insertion checks that supplied standings and head-to-head exactly match the
fixtures. Reading reconstructs these summaries rather than storing redundant
tables. A full league, 230 players and 60 fixtures reads in four queries.
The migration preserves existing roster-only leagues and is reversible; its
downgrade intentionally drops historical fixtures. Use it only on disposable
history or after backing up the data. A complete aggregate is inserted in the
caller's transaction, including all clubs, players and fixtures.

Historical generation does not change player fatigue, morale, cards or suspension.
Those remain initial roster state, not a reconstructed discipline ledger. Live
possessions/events and the planted climax storyline remain separate tasks.
Frozen domain contracts are unchanged.

Run `uv run pytest -q` with `TACTIX_TEST_DATABASE_URL` for PostgreSQL integration.
Tests include known scoreboards, exact table/H2H expectations, all supported
league sizes and context windows, referential integrity, corrupted summaries,
reproducibility, old-version hashes and migration upgrade/downgrade checks.
