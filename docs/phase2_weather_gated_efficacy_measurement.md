# GrainGuard phase 2: weather-gated spray efficacy

This experiment adds weather gating to pesticide application — wind above the label cut-off refuses the pass, rain washes part of the dose off — and measures it against the merged per-Tot tank baseline (`docs/phase2_tank_capacity_measurement.md`: recoverable abiotic stress, lag 3, global quota off, finite tanks on). One feature, one measurement: nothing about tanks, damage, or ecology changed here.

## Mechanism

- `SprayWeatherConfig` (Pydantic, validated): `wind_block_speed_mps` (6.0), `rain_washoff_full_mm` (4.0), `washoff_strength` (1.0). Weather itself is unchanged: the gate reads the `AgWeather` state the adapter already evolves each step.
- Wind at or above the cut-off refuses the application outright. Nothing is sprayed and no product is drawn.
- Rain scales the dose that survives: `retained = 1 - washoff_strength * min(1, precipitation / rain_washoff_full_mm)`, applied as a multiplier on the 0.8 base efficacy. At full `washoff_strength` a rain event at or above the wash-off amount leaves nothing behind, so the application is refused rather than wasted at zero effect.
- The gate is checked **before** the tank. A weather refusal costs the opportunity but not the product, which is the physically honest ordering: an operator who cannot spray today does not empty the tank onto the ground.
- One boom pass is one weather decision (the whole pass is refused or served); each spot request is its own decision, because they happen at different places and times.
- Nothing weather-side reaches the detectors as ground truth. `spray_weather_metrics` is reporting-side only; the weather stream detectors already saw is unchanged.

## Commands

Baseline: the committed 21-seed tank artifacts (`artifacts/phase2_tank_capacity/*`, margin +35.30 pp, resurgence yes). Treatment:

```bash
uv run --no-sync --no-build python scripts/run_designed_reporter_experiment.py \
  --seeds 1000 1001 1002 1003 1004 1005 1006 1007 1008 1009 \
  1010 1011 1012 1013 1014 1015 1016 1017 1018 1019 1020 \
  --steps 400 \
  --pest-damage-lag 3 \
  --sprayer-fleet \
  --spray-weather \
  --workers 2 \
  --out-dir artifacts/phase2_weather_gated
```

```bash
uv run --no-sync --no-build python scripts/run_resurgence_experiment.py \
  --seeds 1000 1001 1002 1003 1004 1005 1006 1007 1008 1009 \
  1010 1011 1012 1013 1014 1015 1016 1017 1018 1019 1020 \
  --steps 150 \
  --pest-damage-lag 3 \
  --sprayer-fleet \
  --spray-weather \
  --out-dir artifacts/phase2_weather_gated_resurgence
```

The designed-reporter batch ran the default arm set, so `oracle_upper_bound` is present as a diagnostic; it is excluded from best-reachable selection as in every earlier phase.

## Designed-reporter measurement

| Measurement | Per-Tot tanks (baseline) | Tanks + weather gating | Change |
|---|---:|---:|---:|
| Static-prior null | 55.76% | 55.76% | 0.00 pp |
| Best reachable precision | 91.05% (`all_designed_seed`) | 92.89% (`all_designed_seed`) | +1.84 pp |
| Exploitable margin | +35.30 pp | **+37.13 pp** | **+1.83 pp** |
| Ordinary (evolved) precision | 42.12% | 70.51% | +28.39 pp |
| Ordinary margin | -13.63 pp | **+14.76 pp** | +28.39 pp |
| Clause-1 slope (`ordinary`) | +0.00669 | -0.00454 | -0.01123 |
| Clause-1 rising seeds (`ordinary`) | 14/21 | 8/21 | -6 seeds |
| Clause-2 correlation (`ordinary`) | -0.0742 | -0.0186 | +0.0556 |
| Clause-2 seeds above 0.2 | 0/21 | 0/21 | 0 |
| Reports per adult lifetime (`ordinary`) | 15.64 | 4.06 | -11.58 |
| Reports per adult lifetime (best arm) | 10.48 | 9.79 | -0.69 |
| Ordinary reports scored | 135,490 | 64,264 | -71,226 |
| Best-arm reports scored | 163,638 | 168,279 | +4,641 |

Precision by arm under weather gating: evolved `ordinary` 70.51%, designed `all_designed_seed` 92.89%, mixed `invasion` 92.28%, static-prior null 55.76%, oracle 100% (diagnostic only).

Weather gating raises the exploitable margin by **+1.83 pp**, the smallest per-feature move in this series so far, and leaves the frozen-pest static-prior null unchanged, as it must.

The large move is on the evolved side: `ordinary` precision rises 42.12% → 70.51% and, for the first time under the tank baseline, sits **above** its own null (+14.76 pp). That is not evidence that the evolved detectors learned anything: their report volume collapses from 135,490 to 64,264 (4.06 reports per adult lifetime, down from 15.64) while the best designed arm's volume is flat. Fewer, later reports against a field that spends more of its time genuinely infested — because ~44% of applications are refused — raise precision arithmetically. Both falsification clauses still fail: the `ordinary` within-run slope is now *negative* (-0.00454, 8/21 seeds rising), the best arm's slope is -0.02592 (1/21 rising), and no seed in any arm clears the 0.2 parent-child correlation threshold. The honest reading is that weather gating makes the field harder to control rather than making detectors better, and the precision gain is a base-rate effect that the clauses correctly refuse to endorse.

## Weather accounting

| Arm | Weather decisions/run | Refused: wind | Refused: rain | Allowed | Allowed but rain-washed | Allowed share | Mean retained efficacy |
|---|---:|---:|---:|---:|---:|---:|---:|
| `ordinary` | 6,967.8 | 2,937.0 | 100.2 | 3,930.6 | 740.5 | 56.5% | 0.932 |
| `all_designed_seed` | 10,750.2 | 4,694.4 | 160.1 | 5,895.7 | 1,028.4 | 54.8% | 0.942 |
| `invasion` | 9,269.3 | 3,935.9 | 129.5 | 5,203.9 | 873.6 | 56.7% | 0.941 |
| `oracle_upper_bound` | 5,342.2 | 1,707.4 | 99.1 | 3,535.8 | 648.7 | 66.3% | 0.938 |

Both mechanisms are load-bearing and wind dominates: at the seasonal wind distribution the domain already generated, 42–44% of application opportunities are refused outright, while rain refuses ~1.5% and shaves the retained dose to 93–94% on average. Spot fulfillment falls accordingly (`ordinary` 30.1% of requests served under tanks-plus-weather, `all_designed_seed` 19.5%).

## Resurgence criterion

| Measurement | Per-Tot tanks (baseline) | Tanks + weather gating |
|---|---:|---:|
| Resurgence verdict | yes | **yes** |
| Indiscriminate minus precise yield | -0.1002 | -0.0936 |
| Indiscriminate minus no-spray yield | -0.0850 | -0.0799 |
| Indiscriminate minus no-spray final pests | +549.6 | +507.4 |
| Indiscriminate sprays applied | 8,800.0 | 6,647.6 |
| Indiscriminate sprays denied | 0.0 | 2,152.4 |
| Precise sprays applied | 358.0 | 282.1 |
| Precise sprays denied | 4,572.0 | 4,655.3 |
| Natural-enemy density, indiscriminate | 104.2 | 452.8 |
| Natural-enemy density, precise | 2,254.9 | 2,274.5 |

**Resurgence survives.** The indiscriminate arm loses ~24% of its applications to wind (5 of 22 boom passes refused per run on average, each pass covering the whole field), and its natural-enemy density therefore ends four times higher than under tanks alone (452.8 vs 104.2). The ecological penalty is weakened but not removed: over-spraying still ends with lower yield than precise spraying (-0.0936) and with more pests than not spraying at all (+507.4), which is what the criterion requires.

This is the mechanism the global quota broke, and it is worth stating why weather gating does not break it the same way: the quota removed pesticide volume in proportion to how much a policy wanted to spray, so the heaviest sprayer was throttled the most. Wind refuses passes at a rate set by the weather, independent of policy, so the indiscriminate arm still applies 6,648 cell-applications against the precise arm's 282. Nothing was tuned to obtain this: the three gate parameters were fixed before the resurgence run, and the run was not repeated with other values.

## Boundary and validation

The gate lives in `src/grain_guard/environment/spray_weather.py` and is enforced in the adapter's spray dispatch. Detectors receive no new stream, and tests assert that no gate metric key carries pest, density, resistance, beneficial, or crop-health state and that no stream label mentions wash-off, blocking, or refusals. Nothing in TattleTots changed.

30 new tests cover config validation, the wind cut-off at and either side of the threshold and its tunability, graded rain wash-off (1.0/0.75/0.5/0.25 retained at 0/1/2/3 mm with a 4 mm full-wash-off), refusal when rain would waste the whole dose, the floor a weaker `washoff_strength` leaves, that rain leaves more pests alive than the same dry application, that a wind refusal leaves pest and beneficial density untouched and draws no product from the tank, that wind refuses a whole boom pass as one decision, counter bookkeeping, and that an unconfigured gate leaves weather irrelevant.

Full validation passed: pre-commit, both Sonar guards, Ruff check and format, mypy strict on `src/`, and 434 strict-marker tests.

Artifacts:

- `artifacts/phase2_weather_gated/designed_reporter_measurement.json`
- `artifacts/phase2_weather_gated/designed_reporter_measurement.md`
- `artifacts/phase2_weather_gated_resurgence/grain_resurgence.json`
- `artifacts/phase2_weather_gated_resurgence/grain_resurgence.md`
