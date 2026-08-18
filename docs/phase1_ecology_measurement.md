# Phase-1 ecology measurement

This measurement asks whether coupling spray decisions to natural enemies, secondary pests, abiotic look-alikes, and patchy dynamics gives localization competence a larger reachable advantage. The before and after arms use one instrument-level convention and differ only by `ecology_config.enabled`.

## Reproduction

All designed-reporter runs freeze pest evolution, use the same published-stream reporter, and use seeds `1000` through `1020` inclusive.

```bash
# After: coupled ecology
uv run --no-sync --no-build python scripts/run_designed_reporter_experiment.py \
  --seeds 1000 1001 1002 1003 1004 1005 1006 1007 1008 1009 \
  1010 1011 1012 1013 1014 1015 1016 1017 1018 1019 1020 \
  --steps 400 \
  --policy-arms ordinary all_designed_seed invasion \
  --workers 1 \
  --out-dir artifacts/phase1_after

# Before: identical instrument with phase-1 ecology disabled
uv run --no-sync --no-build python scripts/run_designed_reporter_experiment.py \
  --seeds 1000 1001 1002 1003 1004 1005 1006 1007 1008 1009 \
  1010 1011 1012 1013 1014 1015 1016 1017 1018 1019 1020 \
  --steps 400 \
  --policy-arms ordinary all_designed_seed invasion \
  --legacy-ecology \
  --workers 1 \
  --out-dir artifacts/phase1_before
```

The resurgence horizon is shorter because at 400 steps every policy approaches crop collapse, making final pest density primarily a dead-host carrying-capacity measurement. At 150 steps the policies retain distinct yield and pest trajectories.

```bash
# After: coupled ecology
uv run --no-sync --no-build python scripts/run_resurgence_experiment.py \
  --seeds 1000 1001 1002 1003 1004 1005 1006 1007 1008 1009 \
  1010 1011 1012 1013 1014 1015 1016 1017 1018 1019 1020 \
  --steps 150 \
  --out-dir artifacts/phase1_after_resurgence_final

# Before: phase-1 ecology disabled
uv run --no-sync --no-build python scripts/run_resurgence_experiment.py \
  --seeds 1000 1001 1002 1003 1004 1005 1006 1007 1008 1009 \
  1010 1011 1012 1013 1014 1015 1016 1017 1018 1019 1020 \
  --steps 150 \
  --legacy-ecology \
  --out-dir artifacts/phase1_before_resurgence_final
```

## Designed-reporter result

| Measurement | Before: legacy ecology | After: coupled ecology |
|---|---:|---:|
| Static-prior localization null | 56.11% | 35.13% |
| Best reachable precision | 81.11% (`all_designed_seed`) | 92.67% (`invasion`) |
| Exploitable margin | +25.00 pp | +57.54 pp |
| Ordinary evolved-arm precision | 22.45% | 18.20% |
| Ordinary margin vs null | -33.66 pp | -16.93 pp |
| Clause 1: ordinary correct-report-rate slope/generation | -0.00476 | +0.00439 |
| Clause 1: ordinary rising seeds | 7/21 | 14/21 |
| Clause 2: ordinary parent-child correlation | -0.0564 | -0.0438 |
| Clause 2: ordinary seeds above 0.2 | 0/21 | 0/21 |
| Ordinary reports scored | 163,656 | 157,251 |
| Ordinary reports/adult lifetime | 21.39 | 19.95 |
| Best-arm reports scored | 144,625 | 65,768 |
| Best-arm reports/adult lifetime | 11.53 | 6.95 |

The internally comparable exploitable margin increased by **32.54 percentage points**. This is not evidence that ordinary evolution learned the detector: ordinary precision remains below the null, clause 1 is small and mixed across seeds, and clause 2 remains far below the approximate `0.2` bar.

## Why this does not contradict the 66.97% null

`docs/response_gate_measurement.md` reports a `66.97%` static-prior null from a different 600-step response-gate experiment with payoff levers and response-gate configurations. Its designed arms reached `68.47%` and `71.13%`, giving the previously reported `+1.50` to `+4.16` pp margins.

The table above is the instrument-level designed-reporter harness at 400 steps with payoff levers 1-4 disabled, correctness weight `0`, the explicit `ordinary`, `all_designed_seed`, and `invasion` arm set, and seeds `1000`-`1020`. Its before null is `56.11%`; its after null is `35.13%`. The 66.97% response-gate result is valid for its own horizon and configuration, but it is not a before baseline for this phase-1 comparison. No margin delta here mixes the two conventions.

## Resurgence result

Resurgence is counted only when indiscriminate spraying both lowers yield relative to precise spraying and ends with more pests than no spraying. The second condition prevents host collapse from masquerading as successful pest control.

| Measurement | Before: legacy ecology | After: coupled ecology |
|---|---:|---:|
| Resurgence verdict | no | yes |
| Indiscriminate minus precise yield | +0.1947 | -0.1628 |
| Indiscriminate minus no-spray yield | +0.7445 | -0.2188 |
| Indiscriminate minus no-spray final pests | -683.6 | +540.2 |
| Indiscriminate minus precise secondary pest-days | +0.0 | +1519.4 |
| Indiscriminate natural-enemy density | 443.0 | 39.1 |
| Precise natural-enemy density | 1048.9 | 618.9 |

Before coupling, indiscriminate spraying improves yield and reduces final pests relative to no spraying. After coupling, it nearly removes natural enemies, releases the secondary pest, lowers yield below the precise policy, and ends above the no-spray pest density.

## Costs and caveats

Two costs are visible in the same artifacts and are not hidden by the headline margin.

| Diagnostic | Before: legacy ecology | After: coupled ecology |
|---|---:|---:|
| Pest-loop parent-child correlation, ordinary arm | +0.2678 | +0.00004 |
| Pest-loop parent-child correlation, best arm | +0.2830 | +0.00034 |
| Mean crop health, pest-free field, step 100 | 0.999 | 0.792 |
| Mean crop health, pest-free field, step 400 | 0.996 | 0.134 |

The pest loop was this domain's one known-good selection gradient and its cell-level parent-child fitness correlation is now indistinguishable from zero. The crop health rows come from a pest-free 10x10 field advanced with a fixed seed, so they isolate the abiotic stressor: it accumulates as unrecovered damage because `CropCell.apply_damage` only ever lowers health, and by 400 steps it, not pest pressure, dominates the state of the field. Part of the null drop from `56.11%` to `35.13%` therefore reflects a field where infestation and damage are widespread rather than only a field where localization is harder to guess.

The correct follow-up is a recoverable abiotic stressor — stress that suppresses growth while soil moisture is low and releases when moisture returns — so the look-alike cause is confusable without being a one-way ratchet toward host collapse. That is a phase-1 correction rather than a phase-2 feature, and it should be measured and attributed separately before any phase-2 work.

## Detector boundary audit

The designed reporter reads only published `pheromone_traps` and `drone_imagery` streams with their declared coordinates. Abiotic stress changes crop health/NDVI-like damage while soil conductivity supplies noisy discriminating information. Secondary-pest pressure enters observable imagery through aggregate pest signal. The reporter does not read crop-field arrays, active locations, abiotic-stress state, pest species identity, or any other ground truth. Oracle reporting is diagnostic-only and was not included in the production arm set or best-reachable selection.

No subsidies, grace periods, juvenile discounts, or population floors were added. The engine and TattleTots models were not changed.

## Phase 2 recommendation

All three proposed additions look worth measuring in separate attributed changes:

- **Lagged irreversible damage** should increase the value of timely evidence rather than only accurate eventual localization.
- **A hard spray budget** should force prioritization among plausible locations instead of allowing evidence quality to be bypassed by treating everything.
- **Weather-gated efficacy** should make action timing consequential and create observable situations where a correct location is not sufficient for a useful response.

They should remain separate experiments: phase 1 already changes both the null and reachable precision substantially, so bundling phase 2 would prevent attribution.

## Artifacts

The generated JSON and Markdown outputs are committed under:

- `artifacts/phase1_before/`
- `artifacts/phase1_after/`
- `artifacts/phase1_before_resurgence_final/`
- `artifacts/phase1_after_resurgence_final/`
