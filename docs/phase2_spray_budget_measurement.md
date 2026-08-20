# GrainGuard phase 2: hard spray budget

> **Superseded, kept as a negative result.** The global per-interval quota measured here is off by default and no later measurement in this series uses it. It raised the exploitable margin by +6.63 pp but destroyed the resurgence criterion, because capping field-wide pesticide volume also caps the collateral kill of natural enemies that makes over-spraying self-defeating. Per-Tot tank capacity replaces it: see `docs/phase2_tank_capacity_measurement.md`. The mechanism and its tests remain in the repository so this failure stays reproducible with `--spray-budget-capacity 60 --spray-budget-interval 7`.

This experiment isolates the second phase-2 feature against the merged lagged-damage baseline. The only treatment difference is a hard domain-side budget of 60 pesticide applications per 7 simulation steps. An omitted budget remains unlimited, so the committed lagged-damage artifacts are the control.

When capacity is scarce, the adapter orders COP dispatch targets by their published `cop_threat_level`; denied targets are not sprayed and do not change pest or beneficial density. This uses only the existing detector output, not field ground truth. Weather-gated efficacy is not included.

## Commands

The unchanged 21-seed lagged-damage artifact is reused as the unlimited control. The finite-budget treatment used:

```bash
PYTHONPATH=src /home/ubuntu/repos/Xylella-SPQR/.venv/bin/python \
  scripts/run_designed_reporter_experiment.py \
  --seeds 1000 1001 1002 1003 1004 1005 1006 1007 1008 1009 \
  1010 1011 1012 1013 1014 1015 1016 1017 1018 1019 1020 \
  --steps 400 \
  --policy-arms ordinary all_designed_seed invasion \
  --pest-damage-lag 3 \
  --spray-budget-capacity 60 \
  --spray-budget-interval 7 \
  --workers 3 \
  --out-dir artifacts/phase2_spray_budget
```

```bash
PYTHONPATH=src /home/ubuntu/repos/Xylella-SPQR/.venv/bin/python \
  scripts/run_resurgence_experiment.py \
  --seeds 1000 1001 1002 1003 1004 1005 1006 1007 1008 1009 \
  1010 1011 1012 1013 1014 1015 1016 1017 1018 1019 1020 \
  --steps 150 \
  --pest-damage-lag 3 \
  --spray-budget-capacity 60 \
  --spray-budget-interval 7 \
  --out-dir artifacts/phase2_spray_budget_resurgence
```

## Designed-reporter measurement

| Measurement | Unlimited lagged baseline | Budget 60 per 7 steps | Change |
|---|---:|---:|---:|
| Static-prior null | 55.76% | 55.76% | 0.00 pp |
| Best reachable precision | 86.83% (`all_designed_seed`) | 93.46% (`all_designed_seed`) | +6.63 pp |
| Exploitable margin | +31.07 pp | +37.71 pp | **+6.63 pp** |
| Ordinary precision | 31.17% | 58.23% | +27.06 pp |
| Ordinary margin | -24.59 pp | +2.47 pp | +27.06 pp |
| Clause-1 slope | +0.01582 | +0.00059 | -0.01524 |
| Clause-1 rising seeds | 15/21 | 8/21 | -7 seeds |
| Clause-2 correlation | -0.1162 | -0.0276 | +0.0886 |
| Clause-2 seeds above 0.2 | 0/21 | 0/21 | 0 |
| Ordinary reports scored | 189,382 | 86,984 | -102,398 |
| Best-arm reports scored | 169,697 | 157,067 | -12,630 |

The hard budget increases the exploitable localization margin by **6.63 percentage points**. It leaves the frozen-pest static-prior null unchanged and improves both designed and ordinary precision, consistent with scarce treatment making target selection consequential rather than allowing every alert to trigger treatment.

The ordinary arm now clears the static-prior null by 2.47 pp, but the evolutionary falsification clauses do not recover: the mean within-run slope is only slightly positive and 13 of 21 seeds are flat or falling; parent-child reproductive correlation remains far below 0.2.

## Budget accounting

| Arm | Mean attempts/run | Mean applied/run | Mean denied/run | Fulfilled |
|---|---:|---:|---:|---:|
| `ordinary` | 7,218.5 | 1,510.0 | 5,708.6 | 20.9% |
| `all_designed_seed` | 10,819.7 | 1,785.6 | 9,034.1 | 16.5% |
| `invasion` | 8,560.5 | 1,623.1 | 6,937.4 | 19.0% |

The selected budget binds strongly in every arm. Tests grade capacities 1, 2, and 3; enforce positive capacity and interval; prove per-interval refill; verify `applied + denied = valid attempts`; prove denied sprays leave pest and beneficial density unchanged; and verify higher published COP threat is served first. Unlimited configuration remains the negative control.

## Resurgence sanity check

| Measurement | Unlimited lagged baseline | Budget 60 per 7 steps |
|---|---:|---:|
| Resurgence verdict | yes | **no** |
| Indiscriminate minus precise yield | -0.1679 | -0.0440 |
| Indiscriminate minus no-spray yield | -0.0850 | -0.0185 |
| Indiscriminate minus no-spray final pests | +549.6 | -1,015.8 |
| Indiscriminate sprays applied | 8,800.0 | 1,320.0 |
| Indiscriminate sprays denied | 0.0 | 7,480.0 |
| Precise sprays applied | 2,742.2 | 986.4 |
| Precise sprays denied | 0.0 | 3,443.2 |

The budget removes the previously measured density-resurgence verdict. Indiscriminate treatment still produces lower yield than precise treatment, but denial limits broad-spectrum mortality enough that it ends with fewer pests than the no-spray policy. This is not tuned away: it is the honest ecological result of imposing scarcity.

## Boundary and validation

The budget is enforced only in the GrainGuard adapter. Detector policies receive no new streams or ground truth. The runner and both measurement scripts pass the validated object configuration without changing TattleTots.

Full validation passed: pre-commit, both Sonar guards, Ruff check and format, mypy, and 375 strict-marker tests. The generated JSON contains no non-finite values.

Artifacts:

- `artifacts/phase2_spray_budget/designed_reporter_measurement.json`
- `artifacts/phase2_spray_budget/designed_reporter_measurement.md`
- `artifacts/phase2_spray_budget_resurgence/grain_resurgence.json`
- `artifacts/phase2_spray_budget_resurgence/grain_resurgence.md`
