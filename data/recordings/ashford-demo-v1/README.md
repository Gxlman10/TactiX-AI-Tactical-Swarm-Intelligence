# Ashford demo recording v1

Portable fallback for the match demonstration. This is a recording of the authored synthetic scenario, not a video, model response, or captured live Foundry run. It contains the complete 90-minute match, league and four event-backed historical fixtures, plus nine deterministic metric/context checkpoints.

| Artifact | Purpose |
|---|---|
| `recording.json.gz` | Canonical JSON payload, gzip compressed (633,620 bytes in the committed build) |
| `manifest.json` | Format/scenario versions, canonical SHA-256, size, match identity, event count, fixture IDs and checkpoint cuts |

The canonical uncompressed payload has 4,623,515 bytes and SHA-256 `6f85661040e08f7606918ce4c0ea7f3033714fe2dce36d00c06e740be97ba1c9`. The checksum covers canonical UTF-8 JSON, not gzip headers or implementation-dependent compression. It detects drift relative to the manifest; it is not a digital signature. The Git revision supplies the reference manifest.

## Verify and replay

From `backend/`, using the existing project environment:

```powershell
uv run python -m tactix.demo.recording verify ../data/recordings/ashford-demo-v1
uv run python -m tactix.demo.recording verify ../data/recordings/ashford-demo-v1 --regenerate
uv run python -m tactix.demo.recording replay ../data/recordings/ashford-demo-v1 --start 3660 --end 3780
```

Normal verification loads the committed bytes without invoking the generator. It validates all five matches, reconciles historical scorer/score ledgers, recomputes every metric and context checkpoint, checks evidence availability and asserts the authored climax. `--regenerate` additionally compares the recorded bundle with today's generator, detecting scenario drift. Both run without PostgreSQL, Azure, Foundry or network access once dependencies are installed.

`replay` emits 121 `ReplayUpdate` NDJSON records for inclusive integer cuts 61:00 through 63:00. It drives the existing `MatchReplay` with a virtual clock, so output is repeatable without sleeping. Sequence numbers retain their full-match identity; events earlier than the start are pre-roll from the checkpoint, not re-delivered by the stream. The complete artifact contains future events by design: consumers must use the cutoff checkpoints or replay output when displaying a partial match.

For actual paced playback, extract a new ordinary MatchResult file and use the existing replay engine:

```powershell
uv run python -m tactix.demo.recording extract ../data/recordings/ashford-demo-v1 --output ../data/generated/recording-match-smoke.json
uv run python -m tactix.simulation.replay --input ../data/generated/recording-match-smoke.json --speed 10000 --start-second 3660
```

These exact commands were run: paced playback finished at 90:00, score 2-2, next sequence 650. Use speed 12 for presentation rather than the smoke-test speed. Extraction refuses to overwrite an existing file; choose another output name for another run. This CLI produces replay data; it does not automatically replace the frontend's short local rehearsal.

## Checkpoint guide

| Clock | Score | Visible events | Climax available | Verified consecutive appearances |
|---|---|---:|---|---:|
| 61:00 | 1-0 | 446 | No | 3 |
| 61:39 | 1-0 | 450 | No | 3 |
| 61:40 | 1-0 | 452 | No | 3 |
| 61:48 | 1-0 | 453 | No | 3 |
| 61:59 | 1-0 | 454 | No | 3 |
| 62:00 | 1-1 | 456 | Yes | 4 |
| 62:08 | 1-1 | 457 | Yes | 4 |
| 63:00 | 1-1 | 458 | Yes | 4 |
| 90:00 | 2-2 | 649 | Yes | 4 |

At 62:00 Finn Hartley's linked shot/goal completes a 20-second midfield-loss transition. Context references the prior Northbridge meeting and Ashford's three latest historical appearances. Four historical cards are not four consecutive prior matches: the older meeting is separate. Hartley's recorded season goal count is ten at this cut. Narrative previews are deterministic authored fixtures, explicitly `agent_inference=false`.

## Rebuild deliberately

```powershell
uv run python -m tactix.demo.recording record ../data/generated/recording-rebuild
uv run python -m tactix.demo.recording verify ../data/generated/recording-rebuild --regenerate
uv run pytest tests/unit/test_recording.py -q
```

Recording requires a new output directory. Canonical serialization sorts keys, excludes wall-clock/environment/session metadata and uses a fixed gzip time/OS header. Tests check byte-identical consecutive builds on the same runtime, canonical equality with this committed artifact, corrupted/truncated payloads, changed manifests, rehashed forged checkpoints, exact replay ordering, repeated playback, future-event exclusion, invalid ranges and extraction overwrite protection. CI validates this committed fallback on every backend run. A deliberate change to the published scenario requires a new scenario version and recording, not silently replacing these reference bytes.
