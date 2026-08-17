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
