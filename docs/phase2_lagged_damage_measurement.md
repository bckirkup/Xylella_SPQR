# GrainGuard phase 2: lagged irreversible damage

This experiment isolates the first phase-2 feature against the merged recoverable-stress baseline. The only treatment difference is `EcologyConfig.pest_damage_visibility_lag_steps`: the baseline uses `0`, while the treatment uses the new default of `3` steps.

Pest injury is committed into a crop-cell queue on the step when feeding occurs. Spraying later cannot remove that queued injury. The injury becomes visible in crop health, yield potential, and imagery after three further field steps. Weed damage remains immediate, and reversible abiotic suppression remains separate from irreversible biotic damage. No sensor publishes the queue or any other ground truth.

## Commands

The phase-1 recoverable artifact is reused as the 21-seed zero-lag baseline because `--pest-damage-lag 0` is the old `_advance_crops` behavior. A three-seed, 400-step zero-lag rerun matched all 9 corresponding committed baseline per-seed records to within 6.49e-12 relative — the largest relative deviation observed, not a bit-for-bit match. Splitting one combined pest-plus-weed `apply_damage` call into a queued pest commit and a separate weed call changes floating-point evaluation order, so the control agrees with the baseline only to floating-point tolerance: 8 of the 9 records differ, by at most 2.4e-15 absolute in the pest parent-child correlation and by at most 6.49e-12 relative across all compared fields. Any wording elsewhere in this series that called the zero-lag control bit-exact is wrong; the claim is tolerance-level agreement.

```bash
PYTHONPATH=src /home/ubuntu/repos/Xylella-SPQR/.venv/bin/python \
  scripts/run_designed_reporter_experiment.py \
  --seeds 1000 1001 1002 \
  --steps 400 \
  --policy-arms ordinary all_designed_seed invasion \
  --pest-damage-lag 0 \
  --workers 1 \
  --out-dir artifacts/scratch_lag0
```

The production lagged-damage run used the same 21 seeds and 400-step horizon as phase 1:

```bash
PYTHONPATH=src /home/ubuntu/repos/Xylella-SPQR/.venv/bin/python \
  scripts/run_designed_reporter_experiment.py \
  --seeds 1000 1001 1002 1003 1004 1005 1006 1007 1008 1009 \
  1010 1011 1012 1013 1014 1015 1016 1017 1018 1019 1020 \
  --steps 400 \
  --policy-arms ordinary all_designed_seed invasion \
  --pest-damage-lag 3 \
  --workers 2 \
  --out-dir artifacts/phase2_lagged_damage
```

```bash
PYTHONPATH=src /home/ubuntu/repos/Xylella-SPQR/.venv/bin/python \
  scripts/run_resurgence_experiment.py \
  --seeds 1000 1001 1002 1003 1004 1005 1006 1007 1008 1009 \
  1010 1011 1012 1013 1014 1015 1016 1017 1018 1019 1020 \
  --steps 150 \
  --pest-damage-lag 3 \
  --out-dir artifacts/phase2_lagged_damage_resurgence
```

## Designed-reporter measurement

| Measurement | Recoverable baseline, lag 0 | Lagged damage, lag 3 | Change |
|---|---:|---:|---:|
| Static-prior null | 56.72% | 55.76% | -0.97 pp |
| Best reachable precision | 88.10% (`invasion`) | 86.83% (`all_designed_seed`) | -1.27 pp |
| Exploitable margin | +31.37 pp | +31.07 pp | **-0.30 pp** |
| Ordinary precision | 30.58% | 31.17% | +0.59 pp |
| Ordinary margin | -26.14 pp | -24.59 pp | +1.55 pp |
| Clause-1 slope | +0.01612 | +0.01582 | -0.00030 |
| Clause-1 rising seeds | 18/21 | 15/21 | -3 seeds |
| Clause-2 correlation | -0.0859 | -0.1162 | -0.0302 |
| Clause-2 seeds above 0.2 | 0/21 | 0/21 | 0 |
| Ordinary reports scored | 193,501 | 189,382 | -4,119 |
| Ordinary reports/adult lifetime | 27.43 | 28.13 | +0.70 |
| Best-arm reports scored | 99,973 | 169,697 | +69,724 |
| Best-arm reports/adult lifetime | 10.58 | 14.43 | +3.85 |

The honest result is flat to slightly worse: the exploitable localization margin falls by **0.30 percentage points**. The lag does what the ecological model requires, but the current precision score asks whether reports localize present pest pressure; it does not directly reward avoiding injury that was committed before visual symptoms appeared. Lagged damage therefore does not, by itself, create a larger measured localization advantage.

Ordinary evolution remains below the static-prior null. Clause 1 remains positive on average, but fewer seeds rise. Clause 2 remains far below the 0.2 bar.

## Resurgence sanity check

| Measurement | Recoverable baseline, lag 0 | Lagged damage, lag 3 |
|---|---:|---:|
| Resurgence verdict | yes | yes |
| Indiscriminate minus precise yield | -0.1503 | -0.1679 |
| Indiscriminate minus no-spray yield | -0.0833 | -0.0850 |
| Indiscriminate minus no-spray final pests | +810.7 | +549.6 |
| Indiscriminate minus precise secondary pest-days | +7071.3 | +7303.6 |
| Indiscriminate beneficial density | 112.2 | 104.2 |
| Precise beneficial density | 1624.6 | 1553.0 |

Resurgence remains real. The lag slightly increases the yield penalty of indiscriminate spraying relative to precise spraying, while the enemy-release mechanism remains intact.

## Boundary and validation

Tests grade reveal timing across 0, 1, and 3 steps; prove committed damage survives later treatment; keep weed injury immediate; preserve legacy immediate damage; verify finite, nonnegative queues and bounded crop state; and verify that the measurement lever is the only config difference between treatment and control arms.

No TattleTots engine or model was changed. No agent subsidy, grace period, juvenile discount, population floor, or ground-truth stream was added.

Artifacts:

- `artifacts/phase2_lagged_damage/designed_reporter_measurement.json`
- `artifacts/phase2_lagged_damage/designed_reporter_measurement.md`
- `artifacts/phase2_lagged_damage_resurgence/grain_resurgence.json`
- `artifacts/phase2_lagged_damage_resurgence/grain_resurgence.md`
