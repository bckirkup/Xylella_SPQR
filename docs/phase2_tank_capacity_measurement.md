# GrainGuard phase 2: per-Tot tank capacity

This experiment replaces the global per-interval spray quota measured in `docs/phase2_spray_budget_measurement.md` with finite per-Tot tank capacity, and measures it against the same merged lagged-damage baseline (recoverable abiotic stress, lag 3, global quota off). One feature, one measurement: weather-gated efficacy is not included.

## Why the global quota was superseded

A field-wide quota is an accountant's constraint. Because it caps total pesticide *volume*, it also caps the collateral kill of natural enemies that phase 1 deliberately added, so it fights the ecological penalty for over-spraying: the quota raised the margin by +6.63 pp but destroyed the resurgence criterion (`resurgence: no`). That negative result is kept in the repository — `SprayBudgetConfig`, its tests, and its measurement document all remain — but the quota is now off by default and no measurement in this series runs with it. It is retained rather than deleted so the failure stays reproducible with a single flag (`--spray-budget-capacity 60 --spray-budget-interval 7`).

Per-Tot capacity makes scarcity local and physical instead: each sprayer Tot carries a finite tank, each application draws a dose, and a Tot that runs dry flies to the refill point and is unavailable for the travel plus the refill. An application spent on a false positive is an application unavailable to a true one nearby, so detection stays an ordinal problem — but field-wide pesticide load is not capped, because a whole-field pass is served by the boom sprayer, which tops up from a nurse tank at the headland.

Equipment stays physical in the repo's sense: tanks and top speeds come from fixed body plans (`BodyPlan.spray_drone`, `BodyPlan.ai_tractor`); only positions and tank levels change. Nothing is heritable here.

## Mechanism

- `SprayerFleetConfig` (Pydantic, validated): `n_spot_sprayers` (8), `spot_tank_liters` (body plan: 20 L), `liters_per_application` (2.0 L), `applications_per_step` (4), `refill_row`/`refill_col` (`None` → mid-field), `refill_duration_steps` (2), and the boom-side knobs `broadcast_enabled`, `broadcast_headland_refill`, `broadcast_tank_liters`, `liters_per_broadcast_cell`, `broadcast_cells_per_step`.
- A spot request is served by the nearest loaded drone that still has beat left this step (ties broken by fleet index, so assignment is deterministic). Flight inside the field is accounted as distance, not charged as downtime; leaving the field to refill is what costs time.
- A drone with less than one dose left departs for the refill point: unavailable for `travel_steps + refill_duration_steps`, where travel is Chebyshev distance at the body plan's top speed.
- Refusals are separated into `empty tank`, `refilling`, and `beat spent`, so it is visible which constraint bound.
- Under scarcity the adapter orders COP dispatch targets by their published `cop_threat_level` only. Denied targets are not sprayed and change no pest or beneficial density. No ground truth reaches that ordering.

## Commands

The committed 21-seed lagged-damage artifact is reused as the unlimited-capacity control (`docs/designed_reporter_measurement.*`, margin +31.07 pp). The finite-tank treatment used:

```bash
uv run --no-sync --no-build python scripts/run_designed_reporter_experiment.py \
  --seeds 1000 1001 1002 1003 1004 1005 1006 1007 1008 1009 \
  1010 1011 1012 1013 1014 1015 1016 1017 1018 1019 1020 \
  --steps 400 \
  --policy-arms ordinary all_designed_seed invasion \
  --pest-damage-lag 3 \
  --sprayer-fleet \
  --workers 2 \
  --out-dir artifacts/phase2_tank_capacity
```

```bash
uv run --no-sync --no-build python scripts/run_resurgence_experiment.py \
  --seeds 1000 1001 1002 1003 1004 1005 1006 1007 1008 1009 \
  1010 1011 1012 1013 1014 1015 1016 1017 1018 1019 1020 \
  --steps 150 \
  --pest-damage-lag 3 \
  --sprayer-fleet \
  --out-dir artifacts/phase2_tank_capacity_resurgence
```

## Designed-reporter measurement

| Measurement | Unlimited lagged baseline | Global quota 60/7 steps (superseded) | Per-Tot tanks | Change vs baseline |
|---|---:|---:|---:|---:|
| Static-prior null | 55.76% | 55.76% | 55.76% | 0.00 pp |
| Best reachable precision | 86.83% (`all_designed_seed`) | 93.46% | 91.05% (`all_designed_seed`) | +4.23 pp |
| Exploitable margin | +31.07 pp | +37.71 pp | **+35.30 pp** | **+4.23 pp** |
| Ordinary (evolved) precision | 31.17% | 58.23% | 42.12% | +10.95 pp |
| Ordinary margin | -24.59 pp | +2.47 pp | -13.63 pp | +10.95 pp |
| Clause-1 slope (`ordinary`) | +0.01582 | +0.00059 | +0.00669 | -0.00913 |
| Clause-1 rising seeds (`ordinary`) | 15/21 | 8/21 | 14/21 | -1 seed |
| Clause-2 correlation (`ordinary`) | -0.1162 | -0.0276 | -0.0742 | +0.0420 |
| Clause-2 seeds above 0.2 | 0/21 | 0/21 | 0/21 | 0 |
| Reports per adult lifetime (`ordinary`) | — | — | 15.64 | — |
| Reports per adult lifetime (best arm) | — | — | 10.48 | — |
| Ordinary reports scored | 189,382 | 86,984 | 135,490 | -53,892 |
| Best-arm reports scored | 169,697 | 157,067 | 163,638 | -6,059 |

Precision by arm under tanks: evolved `ordinary` 42.12%, designed `all_designed_seed` 91.05%, mixed `invasion` 86.80%, static-prior null 55.76% (oracle excluded from best-reachable selection, and not run in this batch).

Finite tanks raise the exploitable margin by **+4.23 pp**, about two thirds of the global quota's +6.63 pp, and leave the frozen-pest static-prior null unchanged. The evolved arm improves by +10.95 pp but — unlike under the global quota — stays **below** its own null, so the quota's one flattering result does not survive the switch. Both falsification clauses still fail: the `ordinary` within-run slope is weakly positive with 14/21 seeds rising, the best arm's slope is negative (-0.02544, 1/21 seeds rising), and no seed reaches the 0.2 parent-child correlation threshold in any arm.

## Tank accounting

| Arm | Attempts/run | Applied | Refused: empty tank | Refused: refilling | Refused: beat spent | Fulfilled | Refills | Liters |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `ordinary` | 7,198.8 | 1,557.2 | 74.2 | 1,573.4 | 3,994.0 | 23.9% | 150.7 | 3,114.4 |
| `all_designed_seed` | 9,221.6 | 1,323.3 | 73.8 | 2,052.6 | 5,771.9 | 14.5% | 128.6 | 2,646.7 |
| `invasion` | 7,923.1 | 1,292.2 | 70.8 | 1,698.1 | 4,862.1 | 16.7% | 125.3 | 2,584.4 |

Scarcity binds in every arm, at fulfillment shares comparable to the global quota's 16.5–20.9%. The immediate refusal reason is usually that the drones on the field had already flown their beat for that step, with refill downtime the next largest cause; `empty tank` is small precisely because a drone that runs dry leaves at once, which converts tank exhaustion into refill downtime. Volume is *not* the binding cap: at ~2,600–3,100 L of spot product plus an uncapped boom, over-spraying stays ecologically expensive.

## Resurgence criterion

| Measurement | Unlimited lagged baseline | Global quota (superseded) | Per-Tot tanks |
|---|---:|---:|---:|
| Resurgence verdict | yes | **no** | **yes** |
| Indiscriminate minus precise yield | -0.1679 | -0.0440 | -0.1002 |
| Indiscriminate minus no-spray yield | -0.0850 | -0.0185 | -0.0850 |
| Indiscriminate minus no-spray final pests | +549.6 | -1,015.8 | +549.6 |
| Indiscriminate sprays applied | 8,800.0 | 1,320.0 | 8,800.0 |
| Indiscriminate sprays denied | 0.0 | 7,480.0 | 0.0 |
| Precise sprays applied | 2,742.2 | 986.4 | 358.0 |
| Precise sprays denied | 0.0 | 3,443.2 | 4,572.0 |
| Natural-enemy density, indiscriminate | — | — | 104.2 |
| Natural-enemy density, precise | — | — | 2,254.9 |

**Resurgence survives.** The indiscriminate arm is served by the boom sprayer and is numerically unchanged from the unlimited baseline (8,800 applications, 0 denied, and identical differences against no-spray), which is exactly the intended contrast with the global quota: capacity is scarce for *targeting*, not for pesticide volume, so broad-spectrum enemy mortality still ends worse than precise spraying.

The precise arm is now much more constrained than under the quota (358 of 4,930 requests served, 7.3%), because the threshold policy asks for every cell above threshold at once, and its yield falls from 0.3300 to 0.2623. The resurgence margin therefore narrows (-0.1679 → -0.1002 yield difference) while the verdict holds. No parameter was tuned to obtain this: the fleet defaults were fixed before the resurgence run.

## Boundary and validation

Tanks, doses, and refills live entirely in `equipment/sprayer_fleet.py` and are enforced in the GrainGuard adapter. Detectors receive no new stream and no fleet state: `sprayer_fleet_metrics` is reporting-side only, and tests assert no stream label mentions tanks, refills, or sprayers, and that no fleet metric key carries pest, density, resistance, beneficial, or crop-health state. Nothing in TattleTots changed.

25 new tests cover config validation (including a dose larger than its tank), graded sensitivity of applications served to tank volume (1/2/3 applications for 2/4/6 L), the within-step beat and its reset, refill departure and return with travel-dependent downtime, distance accounting, that a denied application leaves pest and beneficial density unchanged, that a boom pass survives dry drones, that headland refill off makes broadcast volume bind, and that the last available application goes to the higher published COP threat.

Full validation passed: pre-commit, both Sonar guards, Ruff check and format, mypy strict on `src/`, and 404 strict-marker tests.

Artifacts:

- `artifacts/phase2_tank_capacity/designed_reporter_measurement.json`
- `artifacts/phase2_tank_capacity/designed_reporter_measurement.md`
- `artifacts/phase2_tank_capacity_resurgence/grain_resurgence.json`
- `artifacts/phase2_tank_capacity_resurgence/grain_resurgence.md`
