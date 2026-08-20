---
name: measurement-harness-testing
description: How to verify a GrainGuard measurement harness (designed-reporter arms, gradient arms) is actually measuring what it claims — rerunnability, threshold tamper tests, ground-truth boundary audits, and the price columns that keep a high precision honest. Use when adding to or reviewing scripts/run_designed_reporter_experiment.py, scripts/run_grain_gradient.py, or any new arm measurement in src/grain_guard/analysis/.
---

# Testing a GrainGuard measurement harness

Applies to the arm harness in `src/grain_guard/analysis/` (`arms.execute_arm`,
`designed_reporter.measure_designed_arm`) and the scripts that drive it.

## Rerun on a scratch config, never the production one

Both measurement scripts take an output directory, so a rerun does not have to
touch the committed artifacts:

```bash
# designed-reporter arms: scratch rerun, 2 seeds, short window, scratch dir
uv run --no-sync --no-build python scripts/run_designed_reporter_experiment.py \
  --seeds 1 2 --steps 40 --out-dir scratch_designed_reporter

# production rerun (overwrites docs/designed_reporter_measurement.{json,md})
uv run --no-sync --no-build python scripts/run_designed_reporter_experiment.py --workers 2
```

`--out-dir` is validated by `safe_output_dir`: repository-relative names of
letters, digits, `_`, `-` and `/` only, so `/tmp/...` and `../...` are rejected
before a path is built. Delete the scratch directory afterwards; if you do rerun
into `docs/`, `git restore docs/` puts the committed numbers back.

Budget: one `(arm, seed)` cell at 400 steps is roughly a minute on a 2-core box,
so the full 4-arm × 21-seed default run takes about an hour with `--workers 2`.
Never run it inside a test.

## Compare content, not bytes

`designed_reporter_measurement.json` deliberately stores only the measured
per-seed and per-arm numbers, so two reruns of the same scratch config were in
fact byte-identical here. That property is incidental: `SimulationOutput` stamps
a `timestamp`, so the moment an arm's raw output is written out the artifact stops
being byte-reproducible. Verify a rerun by comparing the `configuration`,
`per_seed`, `arms` and `margin` blocks plus the Markdown, and do not add a CI
check that byte-compares any file containing a `SimulationOutput` dump.

## Prove the evidence threshold is load-bearing

Two traps when tamper-testing a registered reporter policy:

- Patching `GrainEvidenceReporterPolicy.threshold_density`'s dataclass default is
  a no-op, because the engine builds the policy from the registered factory.
  Register a second name instead and pass it through the harness:

  ```python
  register_reporter_policy("...", lambda: GrainEvidenceReporterPolicy(threshold_density=0.0))
  measure_designed_arm(spec, ALL_DESIGNED_ARM, "...")
  ```

- With real infestations present the strongest true detection dominates the
  policy's maximum, so the threshold looks irrelevant. Use a no-event window
  instead: `ArmSpec(pest_intro_probability=0.0)` leaves the field pest-free (cell
  density starts at 0 and logistic growth of 0 stays 0). Then the default
  threshold gives zero designed reports, and a zero threshold gives many
  designed reports of which none are correct.

## Prove a config-gated engine lever is really wired

When an `ArmSpec` field (e.g. `reproduction_correctness_weight`, the lever-5
response gate) is forwarded into `SimulationConfig`, three checks separate
"wired" from "silently dropped":

1. **Default-off**: `simulation_config(ArmSpec(reporting_levers=False, <field>=1.0))`
   must contain none of the lever keys, and
   `SimulationConfig(**run_context(spec).simulation_config)` must equal the
   engine's own default for the field. `SimulationConfig` has no `extra=forbid`,
   so a misspelled key would be silently ignored — always assert on the
   constructed engine object, not just on the dict.
2. **One-key diff**: the config dicts at two lever values must differ in exactly
   that one key (`{k for k in a|b if a.get(k)!=b.get(k)}`).
3. **Graded runtime sensitivity plus a determinism control**: sweep a few values
   (0, 0.25, 0.5, 1.0) on one seed at ~120 steps and require several distinct
   output tuples (precision, clause-1 slope, clause-2 correlation), *and* rerun
   one value twice and require bit-identical output. Without the control, run-to-run
   noise reads as lever sensitivity.

Tamper-test module-level thresholds (e.g. `CLAUSE_2_CORRELATION_THRESHOLD`) by
reassigning the module attribute and re-calling `summarize_policy_arm` — the
count functions read the global at call time, so this works and the count must
move. Do it on both synthetic boundary records (`0.199 / 0.2 / 0.2000001`, to
pin down strict `>`) and on real `per_seed` blocks from a scratch run.

## Audit the ground-truth boundary both ways

- Structurally: assert the feasible-reporter module's own source never names a
  truth accessor (`get_ground_truth`, `get_active_locations`,
  `cells_above_threshold`) or imports `grain_guard.adapter` /
  `grain_guard.environment`.
- At runtime: `measure_designed_arm` reports `oracle_policy_instances`. It must
  be `0` for `ordinary`, `all_designed_seed` and `invasion`, and non-zero only
  for `oracle_upper_bound`.
- On the aggregate: with every feasible arm unscored, `exploitable_margin` must
  return `best_arm=None` and `exploitable_margin_pp=None` — the oracle must
  never be promoted into the reachable-precision slot.

## Pick a scratch window where the null is not degenerate

Short windows can make the margin untestable: at 60 and 120 steps the
designed-reporter `static_prior_null` pins at exactly `1.0`, so
`margin = best - null` is degenerate and no knob can move it. Before sweeping
anything, run one scratch config and check `margin.static_prior_null` is strictly
between 0 and 1. Two seeds × 200 steps gave a null of ~0.64 and took ~52 s with
`--workers 2` — that is the smallest known-good designed-reporter scratch window.
Resurgence scratch runs are cheaper (2 seeds × 100 steps, ~22 s).

## Prove a finite-resource (capacity) config is load-bearing

For a scarcity knob such as `SprayerFleetConfig`, sweep **one knob at a time**
across three values on the same scratch config and require graded, monotone
movement in the served/denied counters — not just "the numbers differ":

| knob | expect as it grows |
|---|---|
| tank volume, sprayer count | `spot_granted` and `spot_fulfilled_share` up, `spot_denied_refilling` down |
| applications per step | `spot_granted` up, `spot_denied_worked_out` down |
| refill duration | `spot_denied_refilling` up, `spot_granted` down |

Then two controls that catch a cosmetic config:

- **Tamper / convergence**: make capacity effectively infinite
  (`--spot-tank-liters 1e6 --n-spot-sprayers 64 --applications-per-step 10000
  --refill-duration 0`). `spot_fulfilled_share` must be exactly `1.0`, all denial
  counters `0`, **and** `best_reachable_precision` / `ordinary_precision` /
  `mean_sprays_applied` must equal the no-flag run *exactly*. An exact match is
  the expectation, because the capacity check should be the only added branch;
  mere "closeness" means the flag perturbs the RNG or the dispatch order.
- **Flag isolation**: with the flag off, every new metric must be `None` and the
  numbers must match `origin/main` run through a `git worktree` with the
  byte-identical command.

## A deliberately uncapped resource needs its own negative control

When a design says one resource is finite but another is *deliberately* not
(here: per-drone spot tanks are finite, boom/broadcast volume is not, because of
headland top-up), "the uncapped arm is unchanged" is only half the proof — an
unwired config would also leave it unchanged. Turn the escape hatch off and show
the arm *does* change:

```python
run_resurgence_arm("indiscriminate", seed, steps=100,
                   sprayer_fleet_config=SprayerFleetConfig(broadcast_headland_refill=False))
```

With top-up on, the indiscriminate arm was identical to no-fleet (8800 sprays,
0 denied); with it off, half the passes were denied and beneficial density rose
an order of magnitude. Note `run_resurgence_experiment` raises
`ValueError: resurgence verdict needs both the indiscriminate and precise
policies`, so to probe a **single** policy call `run_resurgence_arm` per seed and
aggregate with `summarize_policy` instead of asking the experiment for one arm.

## Prove the boundary at runtime with call stacks, not just greps

A structural grep only covers the module you grep. To show the reporter and the
new subsystem never read truth, monkeypatch every truth accessor
(`GrainGuardAdapter.get_ground_truth`, `get_active_locations`, `_pest_severity`,
`CropField.cells_above_threshold`) and wrap `GrainGuardAdapter._field` in a
property that records `traceback.extract_stack()` on each access, then run one
short `measure_designed_arm`. Assert no recorded stack contains a frame from
`reporter_policy.py`, the new subsystem's module, or the reporting/aggregation
functions. Expect the legitimate callers to be exactly engine scoring
(`instrument.validate_instrument`), the domain step (`tattletots_layer.step`) and
dispatch judging — `_field` was touched ~5300 times and none from the reporter.
Also assert the scarcity ordering uses published fields only: give the fleet
capacity for exactly one application and hand it targets whose
`cop_threat_level` order is *inverted* relative to true density; the served cell
must be the highest published threat, and a denied application must leave pest
and beneficial densities bit-identical.

## Price the precision

A designed reporter buys precision with silence, so always publish the price next
to it: raw designed/ordinary report counts, `scoring_reports`, and reports per
adult lifetime. This is also why a designed precision may legitimately exceed the
instrument's `inferability_precision` — it reports on a tiny, easy subset — and
it is what stops a near-100% number reading like a truth leak.

## Renderer honesty

An arm with fewer than `MIN_SCORED_REPORTS` reports must print `unscored`, not
`0.00`, in every precision row, and must not be able to become the best arm.
Check the zero-event case explicitly: a window with no events yields a 0.0 null,
where a 0.00 precision would otherwise render as a tie.

## Validation before a PR

```bash
uv run --no-sync --no-build pre-commit run --all-files
uv run --no-sync --no-build ruff check src/ tests/ scripts/ baselines/
uv run --no-sync --no-build ruff format --check src/ tests/ scripts/ baselines/
uv run --no-sync --no-build mypy src/
uv run --no-sync --no-build pytest --strict-markers -ra
uv run --no-sync --no-build pytest -m smoke
uv run --no-sync --no-build python scripts/sonar_guard.py src tests scripts baselines
uv run --no-sync --no-build python scripts/sonar_guard.py --workflows .github/workflows
```

Keep harness tests to short windows (25-40 steps) so the suite stays minutes,
not hours.

## Spot-check a committed measurement instead of rerunning it

A published table (e.g. `docs/response_gate_measurement.md`) may be 20 seeds ×
600 steps per arm — hours to rerun. Reproducing *one* per-seed row is enough and
costs ~90 s per cell at 600 steps: call `measure_designed_arm` directly with the
same `ArmSpec` and compare the printed slope/correlation/precision/cap-share to
the row. Runs are deterministic per seed, so an exact match is the expectation;
any drift means the committed numbers are stale.

Note `scratch_*` output directories are **not** in `.gitignore`, so they show up
as untracked files in `git status`. Delete them when done.
