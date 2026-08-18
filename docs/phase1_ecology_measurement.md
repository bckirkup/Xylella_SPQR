# Phase-1 ecology measurement

This measurement asks whether coupling spray decisions to natural enemies, secondary pests, abiotic look-alikes, and patchy dynamics gives localization competence a larger reachable advantage. The before and after arms use one instrument-level convention and differ only by `ecology_config.enabled`.

The document reports three states of the same instrument:

1. **Before** — phase-1 ecology disabled (`--legacy-ecology`).
2. **After (ratcheted stress)** — the first coupled implementation, in which drought wrote permanent damage through `CropCell.apply_damage`.
3. **After (recoverable stress)** — the current implementation, in which drought is a reversible, moisture-linked suppression of vigor and only pests and weeds write permanent damage.

State 2 is kept in the tables because most of its headline margin turned out to be an artifact of the ratchet. State 3 is the number to quote.

## Reproduction

All designed-reporter runs freeze pest evolution, use the same published-stream reporter, and use seeds `1000` through `1020` inclusive.

```bash
# After, recoverable stress: coupled ecology under the current code
uv run --no-sync --no-build python scripts/run_designed_reporter_experiment.py \
  --seeds 1000 1001 1002 1003 1004 1005 1006 1007 1008 1009 \
  1010 1011 1012 1013 1014 1015 1016 1017 1018 1019 1020 \
  --steps 400 \
  --policy-arms ordinary all_designed_seed invasion \
  --workers 2 \
  --out-dir artifacts/phase1_after_recoverable

# After, ratcheted stress: the same command at the earlier commit
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
# After, recoverable stress: coupled ecology under the current code
uv run --no-sync --no-build python scripts/run_resurgence_experiment.py \
  --seeds 1000 1001 1002 1003 1004 1005 1006 1007 1008 1009 \
  1010 1011 1012 1013 1014 1015 1016 1017 1018 1019 1020 \
  --steps 150 \
  --out-dir artifacts/phase1_after_recoverable_resurgence

# Before: phase-1 ecology disabled
uv run --no-sync --no-build python scripts/run_resurgence_experiment.py \
  --seeds 1000 1001 1002 1003 1004 1005 1006 1007 1008 1009 \
  1010 1011 1012 1013 1014 1015 1016 1017 1018 1019 1020 \
  --steps 150 \
  --legacy-ecology \
  --out-dir artifacts/phase1_before_resurgence_final
```

## Designed-reporter result

| Measurement | Before: legacy ecology | After: ratcheted stress | After: recoverable stress |
|---|---:|---:|---:|
| Static-prior localization null | 56.11% | 35.13% | 56.72% |
| Best reachable precision | 81.11% (`all_designed_seed`) | 92.67% (`invasion`) | 88.10% (`invasion`) |
| Exploitable margin | +25.00 pp | +57.54 pp | **+31.37 pp** |
| Ordinary evolved-arm precision | 22.45% | 18.20% | 30.58% |
| Ordinary margin vs null | -33.66 pp | -16.93 pp | -26.14 pp |
| Clause 1: ordinary correct-report-rate slope/generation | -0.00476 | +0.00439 | +0.01612 |
| Clause 1: ordinary rising seeds | 7/21 | 14/21 | 18/21 |
| Clause 2: ordinary parent-child correlation | -0.0564 | -0.0438 | -0.0859 |
| Clause 2: ordinary seeds above 0.2 | 0/21 | 0/21 | 0/21 |
| Ordinary reports scored | 163,656 | 157,251 | 193,501 |
| Ordinary reports/adult lifetime | 21.39 | 19.95 | 27.43 |
| Best-arm reports scored | 144,625 | 65,768 | 99,973 |
| Best-arm reports/adult lifetime | 11.53 | 6.95 | 10.58 |

With recoverable stress the honest phase-1 result is an exploitable margin of **+31.37 pp against a before margin of +25.00 pp, a gain of +6.37 pp** — not the +32.54 pp the ratcheted implementation appeared to deliver. Almost the entire apparent gain came from the null: once drought stopped writing permanent damage, the null returned to `56.72%`, statistically indistinguishable in size from the legacy `56.11%`, so the earlier drop to `35.13%` was a field being destroyed rather than a field being harder to guess. What survives the correction is a genuine rise in reachable precision, from `81.11%` to `88.10%`.

This is still not evidence that ordinary evolution learned the detector: ordinary precision (`30.58%`) remains 26 pp below the null, clause 1 is small (`+0.016` per generation), and clause 2 remains negative and far below the approximate `0.2` bar.

The before column is reused rather than re-run: the recoverable-stress change is gated on `ecology.enabled`, and a three-seed `--legacy-ecology` run at this commit reproduces the pre-change legacy numbers exactly (null `0.5476`, best reachable `0.8166`, margin `+26.89` pp on seeds `1000`-`1002` at both commits), as does the three-seed legacy resurgence run.

## Why this does not contradict the 66.97% null

`docs/response_gate_measurement.md` reports a `66.97%` static-prior null from a different 600-step response-gate experiment with payoff levers and response-gate configurations. Its designed arms reached `68.47%` and `71.13%`, giving the previously reported `+1.50` to `+4.16` pp margins.

The table above is the instrument-level designed-reporter harness at 400 steps with payoff levers 1-4 disabled, correctness weight `0`, the explicit `ordinary`, `all_designed_seed`, and `invasion` arm set, and seeds `1000`-`1020`. Its before null is `56.11%`; its current after null is `56.72%`. The 66.97% response-gate result is valid for its own horizon and configuration, but it is not a before baseline for this phase-1 comparison. No margin delta here mixes the two conventions.

## Resurgence result

Resurgence is counted only when indiscriminate spraying both lowers yield relative to precise spraying and ends with more pests than no spraying. The second condition prevents host collapse from masquerading as successful pest control.

| Measurement | Before: legacy ecology | After: ratcheted stress | After: recoverable stress |
|---|---:|---:|---:|
| Resurgence verdict | no | yes | yes |
| Indiscriminate minus precise yield | +0.1947 | -0.1628 | -0.1503 |
| Indiscriminate minus no-spray yield | +0.7445 | -0.2188 | -0.0833 |
| Indiscriminate minus no-spray final pests | -683.6 | +540.2 | +810.7 |
| Indiscriminate minus precise secondary pest-days | +0.0 | +1519.4 | +7071.3 |
| Indiscriminate natural-enemy density | 443.0 | 39.1 | 112.2 |
| Precise natural-enemy density | 1048.9 | 618.9 | 1624.6 |

Before coupling, indiscriminate spraying improves yield and reduces final pests relative to no spraying. After coupling — with or without the ratchet — it nearly removes natural enemies, releases the secondary pest, lowers yield below the precise policy, and ends above the no-spray pest density. The recoverable-stress verdict is not a weaker version of the ratcheted one: yields are higher everywhere because the crop is no longer being destroyed by drought, and the resurgence signal comes from enemy release alone.

Making stress recoverable did require one further correction. With the ratchet removed, the released secondary pest at its full species damage rate collapsed the crop it depended on and starved itself, so indiscriminate spraying ended *below* the no-spray pest density and the verdict flipped to no. `EcologyConfig.secondary_crop_damage_multiplier`, a per-capita crop-damage multiplier on the secondary pest (default `0.2`), keeps enemy release costly without being immediately self-limiting. It is a domain dynamics parameter, not agent scaffolding: it applies to the pest, is independent of any detector's reports, and is gated on coupled ecology so legacy runs are unaffected.

## Costs and caveats

The costs below are visible in the same artifacts and are not hidden by the headline margin.

| Diagnostic | Before: legacy ecology | After: ratcheted stress | After: recoverable stress |
|---|---:|---:|---:|
| Pest-loop parent-child correlation, ordinary arm | +0.2678 | +0.00004 | +0.0138 |
| Pest-loop parent-child correlation, best arm | +0.2830 | +0.00034 | +0.0175 |
| Underlying crop health, pest-free field, step 400 | 0.996 | 0.134 | 0.996 |
| Observed crop vigor, pest-free field, step 400 | 0.996 | 0.134 | 0.548 |

The crop-health rows come from a pest-free 10x10 field advanced with a fixed seed, so they isolate the abiotic stressor. Under the ratchet it accumulated as unrecovered damage and by step 400 dominated the field. Under recoverable stress the underlying health of a pest-free field is back to the legacy `0.996`, while observed vigor still sits at `0.548` in a persistently dry field — the look-alike signal is intact, but it is a suppression that lifts when the soil rewets rather than a one-way slide toward host collapse.

The remaining cost is the pest loop. It was this domain's one known-good selection gradient, and coupling still flattens its cell-level parent-child fitness correlation from `+0.27` to `+0.014`. That is better than the ratcheted `+0.00004` but nowhere near the legacy value: predation, spray mortality, and interspecific competition all now inject cell-level variance that is not inherited, so the pest loop should no longer be cited as this repo's demonstration of a strong heritable gradient.

## Detector boundary audit

The designed reporter reads only published `pheromone_traps` and `drone_imagery` streams with their declared coordinates. Abiotic stress changes the crop health/NDVI-like damage channel, which is where the look-alike lives; the imagery thermal channel and soil moisture/conductivity supply discriminating information, so drought is confusable in the damage channel rather than across the whole imagery vector. Secondary-pest pressure enters observable imagery through aggregate pest signal. The reporter does not read crop-field arrays, active locations, abiotic-stress state, pest species identity, or any other ground truth. Oracle reporting is diagnostic-only and was not included in the production arm set or best-reachable selection.

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
- `artifacts/phase1_after/` (ratcheted stress, retained for comparison)
- `artifacts/phase1_after_recoverable/`
- `artifacts/phase1_before_resurgence_final/`
- `artifacts/phase1_after_resurgence_final/` (ratcheted stress, retained for comparison)
- `artifacts/phase1_after_recoverable_resurgence/`
