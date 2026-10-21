# Synthetic league generator

The generator creates 8–10 fictional clubs using the existing Pydantic `League`
contract. It needs neither a database nor a language model to generate JSON.

From `backend/`:

```sh
uv run python -m tactix.universe --seed 42 --clubs 10
uv run python -m tactix.universe --config ../data/scenarios/league-base.json --output ../data/generated/league-42.json
```

The output file must not already exist. Generated files belong in the ignored
`data/generated/` directory. The versioned configuration records the generator
version, seed, season and club count; command-line options override its values.

## Tactical identities

The fictional names, colours, formations and coaching philosophies are authored
in `universe/profiles.py`. These are design profiles, not imported club data.
The generator varies five numeric ratings by at most four points around each
profile, keeping the tactical contrasts meaningful across seeds.

| Club | Formation | Core design |
|---|---|---|
| Ashford | 4-3-3 | Short build-up, high line and counter-pressure |
| Northbridge | 4-2-3-1 | Deep cover and fast, direct progression |
| Cinderwick Forge | 3-4-3 | Aggressive front press and high wing-backs |
| Merehaven Tides | 4-1-4-1 | Patient short passing through a deep pivot |
| Thornmere Bastion | 5-4-1 | Deep block and strong set-piece rating |
| Vespergate Arrows | 4-4-2 | Fast wide attacks and early crosses |
| Brackenport Weavers | 4-3-2-1 | Narrow central combinations |
| Halewick Lanterns | 3-5-2 | Balanced midfield and wing-back cover |
| Dunvale Kites | 4-2-4 | Fast, wide attacks with exposed midfield space |
| Silverfen Compass | 4-5-1 | Midfield screening and selective progression |

An eight-club league includes the first eight profiles; nine and ten add the
remaining profiles in order. Every club includes a city, nickname, colours,
formation, build-up style, defensive line, pressure, tempo, width, set-piece
rating, philosophy, strengths and vulnerabilities.

Strengths and vulnerabilities are derived from the generated tactical ratings.
They describe intended tactical trade-offs, not findings supported by match
events. Future agents must distinguish these priors from observed evidence.

## Reproducibility and identifiers

```python
from tactix.universe.generator import LeagueConfig, generate_league

config = LeagueConfig(seed=42, club_count=10, season="2026/27")
league = generate_league(config)
```

The same configuration and generator version produce the same JSON and IDs.
Each club uses a private random stream derived from the seed, season, version
and profile key; generation does not alter Python's global random state.
Changing the club count preserves shared tactical ratings but creates a new ID
namespace. Different seeds and seasons also create separate namespaces, allowing
generated leagues to coexist in PostgreSQL.

Changing profile values, selection rules, rating generation or ID construction
requires a new generator version and a reviewed configuration update. Version
`league-v1` accepts integer seeds from 0 through 2^63−1, club counts 8–10 and a
nonblank season string. Invalid inputs and unknown configuration fields fail
validation rather than silently using defaults.

## Persistence and scope

The generated `League` can be passed directly to `add_league` inside a
transaction; see `PERSISTENCE.md`. PostgreSQL tests verify that leagues generated
with different seeds coexist and reconstruct exactly from another session.
Inserting the same configuration twice is still a duplicate insert, not an
update; the persistence API deliberately raises an integrity error.

Squads, fixtures, standings and head-to-head collections are empty. Player
generation, historical results, the planted demo storyline and live simulation
remain separate tasks. Tactical variety alone does not prove match realism;
the simulation layer must use these ratings to influence event probabilities.

Run `uv run pytest -q` for generator, validation and CLI checks. Set
`TACTIX_TEST_DATABASE_URL` as documented in `PERSISTENCE.md` to include the
PostgreSQL round-trip checks.
