# Synthetic player squads

From `backend/`, generate a league with 23 players per club:

```sh
uv run python -m tactix.universe --config ../data/scenarios/league-squads.json
uv run python -m tactix.universe --seed 42 --clubs 10 --output ../data/generated/league-squads-42.json
```

The output file must be new. `league-v2` is now the default; use the versioned
manifest to make the choice explicit. The old `league-base.json` selects
`league-v1` and retains its original club-only output and identifiers.

## Squad construction

Each squad contains 23 players. The first eleven follow an explicit position
map for the club's formation, including one goalkeeper. Twelve reserves add
two goalkeepers, four defenders, three midfielders and three forwards. These
are generated roster slots, not a match-day selection based on form or fitness.
Every formation in the club catalogue has its own map; unknown formations fail
explicitly instead of falling back to a different shape.

Dorsals are unique within a club and run from 1 to 23. Compatible secondary
positions are provided for full-backs/wing-backs, wide midfielders/wingers,
central defenders and several central attacking or midfield roles.

Names are composed from an original fictional vocabulary and unique within a
squad. Different clubs may share names; UUIDs identify players. Northbridge's
starting striker is the fictional Finn Hartley, preserving the name required
by the planned narrative. This introduces no historical goals or results.

The Player contract remains unchanged. A position-based profile is the internal
generation role; no additional domain role field is introduced.

## Attribute generation

Nine profiles distinguish keeper, centre-back, full-back, wing-back, holding
midfielder, central midfielder, creator, wide attacker and striker. Their base
ratings are original design parameters, not learned estimates or licensed data.

Physical, technical and mental families use the fields of the frozen contract.
Every player receives a shared quality offset from −7 to +7 and independent
attribute noise from −6 to +6. Tactical modifiers are then applied, with final
ratings clipped to 20–95 inside the domain's permitted 0–100 range.

| Club parameter | Attribute effect |
|---|---|
| Press intensity | Stamina and work rate: round((press − 50) / 6) |
| Defensive line | Pace: round((line − 50) / 10) |
| Tempo | Acceleration: round((tempo − 50) / 10) |
| Width | Crossing: round((width − 50) / 8) |
| Set-piece rating | Set pieces: round((rating − 50) / 6) |
| Short build-up | Passing +6, first touch +4, decisions +3 |
| Direct build-up | Long passing +6, strength +3, jumping +3 |

These modifiers express squad recruitment fit. They do not yet prove how a
player performs in simulated events. Position is the main profile driver;
the shared quality offset creates variation between players of the same role.
Age and height do not currently alter attribute ratings.

Only goalkeepers receive the goalkeeping family. Their ratings start at 70,
with the shared quality offset and independent noise from −9 to +9. Reflexes
receive +3, short build-up adds +6 distribution, and line height affects sweeping
by round((line − 50) / 6). Values are clipped to 20–95.

Players are 18–35 years old. Goalkeepers and central defenders are 183–202 cm;
other positions are 165–194 cm. Left-sided positions have an 85% left-foot
probability; other positions have an 18% probability. Weak-foot ratings are 1–5.
Initial state has zero fatigue, zero cards, no suspension and morale of 50–80.
History generation will have to establish season-specific state later.

## Explainable tendencies

The primary position sets a design hot zone and selects role-relevant attributes.
Two favoured actions come from the highest selected design ratings; two relative
limitations come from the lowest. A striker's limitations focus on attack and
support rather than on a low marking rating that is peripheral to that role.
Each phrase includes the actual numeric rating. Goalkeepers use their own
attribute candidates. Limitations are relative to the player's profile, not
claims of poor performance or findings from previous matches.

For example, a winger with dribbling 95 and finishing 20 receives a preference
for take-ons and a finishing limitation. Changing those attributes and running
`derive_tendencies(player)` changes the explanation. Simulation and agents must
use observed events separately when claiming successful actions or patterns.

## Reproducibility, integration and checks

`generate_squad(club, seed)` returns a new list without modifying the club. Its
namespace includes the club ID, seed and squad version. Each player slot has a
separate random stream, preserving deterministic output and global random state.
The full league configuration produces globally unique player IDs across clubs.

`league-v2` uses a different league/club namespace from `league-v1`; both versions
can coexist in PostgreSQL. Their club tactical ratings are identical for the same
seed, season and club count. No schema migration is needed: all player fields
already round-trip through the persistence layer.

Tests cover all ten formations through leagues of 8–10 clubs, multiple seeds,
role differentiation, causal tactical modifiers, tendency explanations, CLI
reproducibility, v1 compatibility and complete PostgreSQL reconstruction.
Run `uv run pytest -q` with `TACTIX_TEST_DATABASE_URL` configured as described in
`PERSISTENCE.md` to include the integration checks.
