# Detector-side selection gradient vs the pest reference loop

## Question

Does the TattleTots grounded-input fix (PR #55, branch
`devin/1786813382-grounded-stream-access`) produce a *functional* evolutionary
gradient on the agent/detector side of GrainGuard — one where reporting
correctly pays in offspring — using the pest loop in
`src/grain_guard/environment/pest.py` as the reference shape of a working
gradient?

Answer, up front: **no.** The fix does exactly what it claims mechanically
(grounded-yield share rises from `0.110` to `1.000`, report precision rises
from `0.350` to `0.506`), but the detector side still has no functional
gradient: parent-child reproductive correlation stays at zero
(`-0.015` to `+0.048`, `0 of 30` seeds above the `0.2` target) while the pest
reference reaches `0.207`–`0.222` in the same runs, arm-mean precision never
clears its static-prior null (`0.549`), and the correct-report rate *falls*
within every run, falling further the more grounded input agents get.

## Design

The pest adversary is held fixed for every detector-side measurement, because a
coevolving adversary can hide or fake detector improvement. The freeze is an
explicit config option, `freeze_pest_evolution`, that reaches `PestPopulation`
via `CropField` and `GrainGuardAdapter`, and is settable from a domain config
(`adapter_kwargs_from_config`). Frozen pests still consume their random draws,
so a frozen run stays seed-aligned with an evolving run; only the heritable
state (resistance frequency, night feeding, underside preference, edge refuge)
stops changing. Density, damage, dispersal, and every other ecological process
keep running. No scaffolding of any kind was added: no subsidies, grace
periods, juvenile discounts, or population floors, and no parameter is changed
mid-run.

Arms, 10 seeds each (42–51), 400 steps, 20x20 monoculture field, identical
configuration apart from the knob under test:

| Arm | `grounded_input_fraction` | Pest evolution |
| --- | ---: | --- |
| `detector_gif0` (baseline) | 0.00 | frozen |
| `detector_gif0.34` | 0.34 | frozen |
| `detector_gif0.67` | 0.67 | frozen |
| `pestref_gif0` | 0.00 | evolving |
| `pestref_gif0.67` | 0.67 | evolving |

Estimators (`src/grain_guard/analysis/gradient.py`) are shared by both sides so
the comparison is apples-to-apples:

- selection differential `cov(trait, w) / mean(w)`, in trait units;
- heritability as the parent-offspring regression slope for clonal lineages,
  with its correlation;
- parent-child reproductive correlation, the correlation between a parent's
  and its offspring's reproductive output;
- opportunity for selection `var(w) / mean(w)^2`, and raw fitness variance.

Reproducing unit and focal trait per side:

| | Detector side | Pest side |
| --- | --- | --- |
| Unit | engine agent (matured cohort, first seen in the first 75% of the run) | grid cell (clonal pest line) |
| Fitness | offspring count | per-capita density change over one 14-step generation |
| Focal heritable trait | genome escalation threshold | night-feeding fraction |
| Function measure | correct-report rate | (none; damage is its payoff) |

Every estimator returns `None` rather than a misleading `0` when its sample is
degenerate, and a trait whose spread is only floating-point noise (as for a
frozen pest trait after dispersal rewrites values) is treated as having no
variance, so frozen arms report `heritability = None`, not a spurious `1.0`.

## Nulls

Two nulls accompany every precision number, both from
`tattletots.interface.instrument.validate_instrument` on a fresh adapter of the
same configuration: the static-prior null (always guess the single most likely
location) and the uniform/chance null (`1/400` cells). The engine's own
`static_prior_precision` and `chance_precision` from the run are reported
alongside. All 50 runs passed instrument validation
(`instrument_valid = 10/10` per arm), with inferability precision `0.932`.

| Null | Value |
| --- | ---: |
| Instrument static-prior null | 0.5495 (SD 0.0385) |
| Instrument uniform/chance null | 0.0025 |
| Engine static-prior precision (per arm) | 0.482 / 0.512 / 0.519 (detector arms) |
| Engine chance precision (per arm) | 0.215 / 0.221 / 0.227 (detector arms) |

## Detector-side results (pest frozen)

Mean (SD) over 10 seeds.

| Metric | `gif=0.0` (baseline) | `gif=0.34` | `gif=0.67` | Null / target |
| --- | ---: | ---: | ---: | --- |
| Report precision | 0.350 (0.202) | 0.390 (0.105) | 0.506 (0.165) | 0.549 static prior; 0.0025 uniform |
| Seeds above static prior | 2/10 | 1/10 | 5/10 | — |
| Grounded-yield share | 0.110 (0.120) | 0.792 (0.049) | 1.000 (0.000) | — |
| Effective grounded-yield share | 0.167 | 0.823 | 1.000 | — |
| Per-capita attention solvency | 0.245 (0.077) | 0.263 (0.039) | 0.311 (0.071) | — |
| Attention capacity per capita | 0.981 | 0.920 | 1.065 | 1.0 = break-even |
| Correct-report rate, first half | 0.391 (0.207) | 0.487 (0.071) | 0.604 (0.098) | — |
| Correct-report rate, second half | 0.076 (0.154) | 0.062 (0.080) | 0.112 (0.123) | — |
| Rate delta (second − first) | −0.315 | −0.424 | −0.492 | > 0 wanted |
| Seeds with positive delta | 1/10 | 0/10 | 0/10 | — |
| Parent-child reproductive correlation | −0.014 (0.110) | +0.048 (0.101) | −0.015 (0.074) | > 0.2 wanted |
| Seeds above 0.2 | 0/10 | 0/10 | 0/10 | — |
| Heritability (escalation threshold) | 0.843 (0.028) | 0.857 (0.029) | 0.853 (0.022) | — |
| Parent-offspring trait correlation | 0.837 | 0.853 | 0.847 | — |
| Selection differential (trait) | +0.0021 | +0.0026 | +0.0010 | — |
| Selection differential on function | +0.0072 | +0.0082 | +0.0322 | — |
| Opportunity for selection | 2.413 (2.305) | 1.039 (0.295) | 1.250 (0.444) | — |
| Fitness variance | 2.528 | 1.101 | 1.252 | — |
| Mean fitness | 1.016 | 1.032 | 1.007 | 1.0 = break-even |
| Reproducing fraction of cohort | 0.594 | 0.672 | 0.636 | — |

Engine-flagged degeneracy reasons per 10 runs:

| Reason | `gif=0.0` | `gif=0.34` | `gif=0.67` |
| --- | ---: | ---: | ---: |
| `precision_not_above_static_prior` | 9 | 10 | 6 |
| `grounded_yield_share_below_minimum` | 10 | 0 | 0 |
| `attention_insolvency_with_capacity_overshoot` | 6 | 10 | 6 |

## Pest-vs-detector comparison (same estimators)

Detector columns are the frozen-pest arms; pest columns are the evolving
`pestref` arms at the same seeds, since a frozen pest has zero trait variance
by construction and cannot supply a reference gradient.

| Estimator | Detector `gif=0.0` | Detector `gif=0.34` | Detector `gif=0.67` | Pest `gif=0.0` | Pest `gif=0.67` |
| --- | ---: | ---: | ---: | ---: | ---: |
| Parent-child reproductive correlation | −0.014 | +0.048 | −0.015 | **+0.222** | **+0.207** |
| Seeds above 0.2 | 0/10 | 0/10 | 0/10 | 3/10 | 4/10 |
| Heritability | 0.843 | 0.857 | 0.853 | 0.990 | 0.990 |
| Parent-offspring trait correlation | 0.837 | 0.853 | 0.847 | 0.997 | 0.997 |
| Selection differential (trait units) | +0.0021 | +0.0026 | +0.0010 | +0.00002 | +0.00017 |
| Trait variance | 0.0249 | 0.0176 | 0.0204 | 0.0022 | 0.0021 |
| Opportunity for selection | 2.413 | 1.039 | 1.250 | 0.066 | 0.038 |
| Fitness variance | 2.528 | 1.101 | 1.252 | 0.089 | 0.046 |
| Mean fitness | 1.016 | 1.032 | 1.007 | 1.151 | 1.102 |

The two sides fail and succeed in opposite ways. The pest loop works with
*small* fitness variance near break-even (`I = 0.04`–`0.07`, `w̄ ≈ 1.1`),
near-perfect transmission (`h² ≈ 0.99`, trait correlation `0.997`), and a
consistently positive parent-child fitness correlation (`≈ 0.21`): each cell's
reproductive success predicts its descendant's, so a tiny per-generation
selection differential (`1.7e-5`–`1.7e-4`) accumulates — night feeding moves
`0.100 → 0.566` and resistance `0.010 → 0.029`/`0.057` over 400 steps.

The detector side has the ingredients but not the coupling. Transmission is
fine (`h² ≈ 0.85`) and there is 20–60x more fitness variance than the pest side
(`I = 1.0`–`2.4` vs `0.04`–`0.07`), but that variance is nearly independent of
function: the parent-child reproductive correlation is zero, the selection
differential on the heritable escalation threshold is `0.001`–`0.003`, and
selection on realized function (correct-report rate) is `0.007`–`0.032`. Agent
reproductive success is noise, not accumulated performance, so nothing the fix
delivers upstream can be retained downstream.

## What the fix does and does not fix

Does fix (monotonic in `grounded_input_fraction`):

- Grounded input actually reaches agents: grounded-yield share `0.110 → 0.792 →
  1.000`; `grounded_yield_share_below_minimum` disappears above `0.0`.
- Report precision rises `0.350 → 0.390 → 0.506`, and seeds clearing the
  static-prior null go `2 → 1 → 5` of 10.
- First-half correct-report rate rises `0.391 → 0.487 → 0.604`.
- Per-capita attention solvency rises `0.245 → 0.263 → 0.311`.

Does not fix:

- Arm-mean precision still sits below the static-prior null (`0.549`) at every
  fraction, so on average the detector is beaten by "always guess the most
  likely cell".
- Parent-child reproductive correlation stays at zero at every fraction; the
  `>0.2` target is met by `0/30` detector runs and only by the pest side.
- The within-run trajectory points the wrong way and gets *worse* with more
  grounding: rate delta `−0.315 → −0.424 → −0.492`, positive in `1/30` runs.
  More grounded evidence raises early accuracy but that accuracy is not
  retained, so the second half collapses to `0.06`–`0.11`.
- `attention_insolvency_with_capacity_overshoot` persists at every fraction.

## Coevolution measurement hazard, quantified

Comparing the frozen and evolving arms at the same seeds shows why the freeze
matters: with the pest left evolving, detector precision at `gif=0.67` reads
`0.572` instead of `0.506` (+0.066), and at `gif=0.0` reads `0.380` instead of
`0.350`. Leaving the adversary in motion flatters detector precision by roughly
the size of one full step of the grounding knob, so an unfrozen comparison
would have overstated the fix.

Freeze validity check: in every frozen arm, mean night feeding stays
`0.1000 → 0.1000` and resistance `0.0100 → 0.0100` across 400 steps with pest
trait variance exactly `0.0` (heritability correctly reported as `None`), while
the matched evolving arms move to `0.566` and `0.029`/`0.057`. Density keeps
responding in both.

## Reproduction

The TattleTots branch build is installed into the venv only
(`uv pip install --no-deps -e ~/repos/TattleTots` at TattleTots commit
`32da56a`); `uv.lock` is unchanged and still pins the merge-base revision, so
this measurement is not reproducible from the lockfile alone.

```bash
# TattleTots branch build in the venv (lockfile untouched)
git clone https://github.com/bckirkup/TattleTots.git ~/repos/TattleTots
git -C ~/repos/TattleTots checkout devin/1786813382-grounded-stream-access
uv sync --locked --no-build --no-binary-package domain-runner \
  --no-binary-package grain-guard --no-binary-package tattletots --extra dev
uv pip install --no-deps -e ~/repos/TattleTots

# 50 runs: 3 detector arms + 2 pest reference arms x 10 seeds
uv run --no-sync --no-build python scripts/run_grain_gradient.py \
  grain_gradient_output --steps 400 --seeds 42 43 44 45 46 47 48 49 50 51
```

Every run writes a unified `tattletots.output_schema.SimulationOutput` JSON
with the gradient metrics under `domain_metrics`. Committed here:

- `docs/grain_detector_gradient/gradient_summary.json` — per-arm means plus the
  full `domain_metrics` record of all 50 runs.
- `docs/grain_detector_gradient/{detector_gif0,detector_gif0.34,detector_gif0.67,pestref_gif0,pestref_gif0.67}_s42.json`
  — full `SimulationOutput` for seed 42 of each arm (the remaining 45 run files
  are regenerated by the command above).
