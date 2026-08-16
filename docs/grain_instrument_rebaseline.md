# GrainGuard instrument-contract re-baseline

## What changed

The GrainGuard adapter now publishes a spatial instrument contract for every
raw stream. The public location frame is the inclusive `CropField` extent.
Trap, weather-station, and soil-sensor feature blocks repeat their fixed
sensor coordinates and declare their feature modalities. Satellite features
use the owning 5x5 zone centroid together with the zone's row/column
footprint; they are not declared as cell-level point observations.

Satellite observations are marked `observed` on revisit steps and `missing`
off cadence. Off-cadence numeric values remain stale for compatibility with
the existing stream object, but dynamic coordinates are cleared and static
sensor geometry remains populated, so staleness is visible to agents.
Trap, weather, and soil features are observed on every step because their
implemented sensors have no additional availability cadence.

The incumbent decoder had two geometry bugs. It treated the 10-trap by
2-feature vector as a flattened field and mapped a peak with field-width
arithmetic, so trap reports were effectively forced onto row zero. Its
satellite fallback made the same assumption for the 5x5x3 zone vector.
Decoding now maps trap features to their owning trap and satellite features
to their owning zone centroid. Zone footprints preserve the evidence's
coarse spatial support rather than inventing cell-level precision.

The sensor audit found no hidden-state violation in the published path:
satellite reads crop observations, traps read the pest population at their
fixed cells, soil probes read their crop cells, and weather stations read
the weather object. Agents now also receive scheduled drone imagery and
harvest-time yield streams. The drone follows a deterministic geography-only
sweep (`time_step` modulo the field cells), never selecting targets from
infestation state. Its imagery is event-detection evidence. Yield monitoring
is gated only by crop maturity (more than half of cells mature or harvested),
is contextual/lagging evidence, and is explicitly marked missing before
harvest.

Metadata and statuses were tested against low-pest and heavy-infestation
fields with identical sensor configurations. Their coordinates, static
geometry, footprints, and statuses remain identical at the same steps.

## Instrument measurements

The comparison below uses 20 seeds (42–61), 200 steps per seed, and the same
TattleTots build. The baseline is the post-#17 Grain adapter at commit
`4a1dd6f`; the after result is this branch. The earlier `0.579` decoder
precision was the pre-#17 result and is retained only as historical context.

| Metric | Post-#17 baseline (`4a1dd6f`) | Drone + yield branch |
| --- | ---: | ---: |
| Decoder precision (mean) | 0.8814 (SD 0.0568) | 0.8864 (SD 0.0377) |
| Inferability precision (mean) | 0.9461 | 0.9603 |
| Static-prior null (mean) | 0.6978 | 0.6908 |

The pre-#17 decoder precision was `0.579`; it is not the baseline for this
branch. Relative to the post-#17 baseline, publishing drone imagery and yield
monitoring is neutral-to-slightly-positive on localization: decoder precision
increases from `0.8814` to `0.8864`, and inferability increases from `0.9461`
to `0.9603`, while the static-prior null remains approximately `0.69`.
Twelve seeds improved in decoder precision and eight worsened. The seed-42
single-seed comparison goes from `0.9549` to `0.9203` and would tell the
opposite story; the new sensor calls consume RNG draws and shift the
trajectory, so single-seed results are fragile and should not be quoted from
this file.

`satellite_indices` declares 75 features, and the engine cap was 30, so the
stream was silently truncated before agents saw it and declared satellite
feature indices 30–74 reached no agent. The cap is now 75, so every declared
satellite feature is deliverable, and the TattleTots conformance suite checks
declared feature counts against the deliverable ceiling so this class of
mismatch cannot recur silently.

The prior cap-effect measurement was monoculture-only and used an earlier
engine. It reported mean agent report precision of `0.4715` at cap 30 and
`0.4423` at cap 75, against static-prior nulls of `0.6331` and `0.6624`,
respectively. Those values remain as a labeled prior-engine measurement; they
are not overwritten by the current remeasurement.

The current engine remeasurement adds orchard coverage and uses the same
800-step, five-seed-per-arm design for caps 30 and 75:

| Landscape | Cap | Mean agent report precision | Mean static-prior null |
| --- | ---: | ---: | ---: |
| Monoculture | 30 | 0.4671 | 0.5439 |
| Monoculture | 75 | 0.5142 | 0.5656 |
| Orchard | 30 | 0.3682 | 0.4717 |
| Orchard | 75 | 0.4392 | 0.5347 |

The prior and current measurements differ, and the direction of the cap
effect is engine-dependent: under the current engine, cap 75 is higher than
cap 30 by `0.0470` in monoculture and `0.0710` in orchard, but that is not a
general claim that raising the cap improves performance. Every current arm
remains below its static-prior null. All 20 current runs were flagged
`initiation_is_degenerate`; all 20 had
`grounded_yield_share_below_minimum`, 17 had
`precision_not_above_static_prior`, and 2 had
`attention_insolvency_with_capacity_overshoot`. The cap correction therefore
does not demonstrate competence above the null.

The agent-level arms above are engine-coupled measurements. The 20-seed
instrument-level table above them is adapter-side and unchanged. The cap
correction remains justified as contract honesty: declared geometry that no
agent can receive is not published evidence.

### Current cap-effect provenance

- Grain source commit: `085d463b545db94cd9b058455bc6ed3e10c85453`
- TattleTots engine commit: `cee59f93f6973fa7fefb2f87dbb40a8ce0095113`
- Harness: `scripts/run_grain_cap_effect.py`
- Command:
  `uv run --no-sync --no-build python scripts/run_grain_cap_effect.py ./grain_cap_effect_output`
- Steps: `800`
- Seeds: `42–46` (five seeds per arm)
- Landscapes: monoculture and orchard
- Caps: `30` and `75`
- Workers: `5`
- Raw per-run output is not committed. Regenerate it with the command above;
  the output will be written to `./grain_cap_effect_output/key.json`.

Final validator findings:

- `event_window`: passed — the measured window contains observable event
  variation.
- `coordinate_frame`: passed — ground-truth and report locations stay within
  the declared frame.
- `baseline`: passed — static-prior precision remains approximately 69% and
  serves as the localization competence null.
- `localization`: passed — localization is non-vacuous across multiple event
  locations.
- `inferability`: passed — published evidence carries event locations above
  uniform chance.
- `declarations`: passed — stream lengths, statuses, and metadata declarations
  are consistent.

This result is a contract measurement, not a designed-reporter result.

## Per-seed measurements

| Seed | Baseline decoder | After decoder | Baseline inferability | After inferability | Baseline static prior | After static prior |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 42 | 0.954887 | 0.920290 | 0.969925 | 0.934783 | 0.691729 | 0.688406 |
| 43 | 0.955882 | 0.906475 | 0.955882 | 0.942446 | 0.705882 | 0.683453 |
| 44 | 0.870504 | 0.896296 | 0.906475 | 0.940741 | 0.669065 | 0.681481 |
| 45 | 0.961240 | 0.865672 | 0.968992 | 0.992537 | 0.720930 | 0.701493 |
| 46 | 0.939850 | 0.933333 | 0.947368 | 0.955556 | 0.736842 | 0.681481 |
| 47 | 0.910448 | 0.906475 | 0.932836 | 0.942446 | 0.716418 | 0.690647 |
| 48 | 0.861314 | 0.923077 | 0.927007 | 0.976923 | 0.686131 | 0.700000 |
| 49 | 0.866667 | 0.909091 | 0.918519 | 0.962121 | 0.696296 | 0.712121 |
| 50 | 0.940741 | 0.888112 | 0.962963 | 0.951049 | 0.688889 | 0.671329 |
| 51 | 0.762963 | 0.824427 | 0.933333 | 0.984733 | 0.688889 | 0.717557 |
| 52 | 0.938931 | 0.911765 | 0.961832 | 0.933824 | 0.709924 | 0.683824 |
| 53 | 0.878788 | 0.918519 | 0.924242 | 0.970370 | 0.734848 | 0.688889 |
| 54 | 0.868613 | 0.893939 | 0.934307 | 0.984848 | 0.693431 | 0.704545 |
| 55 | 0.800000 | 0.805755 | 0.935714 | 0.935252 | 0.671429 | 0.654676 |
| 56 | 0.848485 | 0.851852 | 0.954545 | 1.000000 | 0.719697 | 0.703704 |
| 57 | 0.878788 | 0.865248 | 0.977273 | 0.936170 | 0.689394 | 0.666667 |
| 58 | 0.816176 | 0.823529 | 0.926471 | 1.000000 | 0.691176 | 0.713235 |
| 59 | 0.843972 | 0.900709 | 0.929078 | 0.921986 | 0.659574 | 0.673759 |
| 60 | 0.819549 | 0.856061 | 0.969925 | 0.969697 | 0.684211 | 0.704545 |
| 61 | 0.910448 | 0.927007 | 0.985075 | 0.970803 | 0.701493 | 0.693431 |
