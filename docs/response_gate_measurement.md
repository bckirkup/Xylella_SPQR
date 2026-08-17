# Response-gate measurement: does lever 5 move either falsification clause here?

TattleTots' falsification test (`TattleTots/docs/initiation.md`) is cleared on a real
instrument with a non-vacuous static-prior null only if either

- **clause 1**: the correct-report rate rises over generations *within* a run, with no
  change of initial parameters, or
- **clause 2**: the parent-child reproductive correlation is reliably above `~0.2`.

Lever 5, the response gate (`reproduction_correctness_weight`, `W`), mixes fractional
rank in verified correctness (`correct_reports / (reports_issued + 2)`) into the
reproductive merit a binding population cap rations by. On TattleTots'
`SparseSensorScenario` it cleared clause 1 and not clause 2. This document reports the
same measurement on the grain instrument.

**Verdict: neither clause moves here.** `W=1` leaves clause 1 indistinguishable from
noise (12/20 rising seeds versus 9/20 at `W=0`, mean slope negative in both) and leaves
clause 2 further from the bar than the control (0/20 seeds above `0.2` versus 1/20, mean
`-0.002` versus `+0.016`). The result replicates on an independent holdout seed block.
The domain's own pest loop, measured in the same runs, sits at parent-child
`r = +0.19..+0.27`, so the metric can register a real reproductive gradient in this
environment — the detector loop simply does not have one.

## Reproduction

The measurement runs from the lockfile — no editable install — against
`tattletots @ 5c1534a6b1dd5fe4f5ddabce54b8b3733af1cf6c` (TattleTots `main`, lever 5).

```bash
uv sync --locked --no-build \
  --no-binary-package grain-guard --no-binary-package domain-runner \
  --no-binary-package tattletots --extra dev

# main seed block (20 seeds, 600 steps): control then treatment
uv run --no-sync --no-build python scripts/run_designed_reporter_experiment.py \
  --steps 600 --workers 2 --payoff-levers --policy-arms ordinary \
  --correctness-weight 0 --out-dir scratch_gate/w0_main --seeds $(seq 1000 1019)
uv run --no-sync --no-build python scripts/run_designed_reporter_experiment.py \
  --steps 600 --workers 2 --payoff-levers --policy-arms ordinary \
  --correctness-weight 1 --out-dir scratch_gate/w1_main --seeds $(seq 1000 1019)

# independent holdout seed block (12 seeds)
uv run --no-sync --no-build python scripts/run_designed_reporter_experiment.py \
  --steps 600 --workers 2 --payoff-levers --policy-arms ordinary \
  --correctness-weight 0 --out-dir scratch_gate/w0_holdout --seeds $(seq 2000 2011)
uv run --no-sync --no-build python scripts/run_designed_reporter_experiment.py \
  --steps 600 --workers 2 --payoff-levers --policy-arms ordinary \
  --correctness-weight 1 --out-dir scratch_gate/w1_holdout --seeds $(seq 2000 2011)

# designed-reporter ceiling under the same config, both weights
uv run --no-sync --no-build python scripts/run_designed_reporter_experiment.py \
  --steps 600 --workers 2 --payoff-levers --policy-arms all_designed_seed \
  --correctness-weight 0 --out-dir scratch_gate/w0_designed --seeds $(seq 1000 1019)
uv run --no-sync --no-build python scripts/run_designed_reporter_experiment.py \
  --steps 600 --workers 2 --payoff-levers --policy-arms all_designed_seed \
  --correctness-weight 1 --out-dir scratch_gate/w1_designed --seeds $(seq 1000 1019)
```

`--payoff-levers` and `--correctness-weight` are both off/zero by default, so the
committed `docs/designed_reporter_measurement.md` numbers are unaffected by this work.
The scratch output directory keeps these runs out of the committed artifacts; per-arm
JSON stamps a timestamp and is not byte-comparable, so reruns are compared on the
configuration, `arms`, `margin` and `per_seed` blocks.

## Fixed configuration

Identical in every arm below; `W` is the only difference between control and treatment
(asserted in `tests/test_designed_reporter.py::TestResponseGateConfig`).

| Setting | Value |
|---|---|
| `correct_report_attention_value` | `8.0` |
| `reproduction_merit_ordering` | `True` |
| `escalation_calibration_in_score_units` | `True` |
| `false_alarm_break_even_precision` | `0.2` |
| `gene_pool.escalation_threshold_range` | `(0.05, 0.3)` |
| `reproduction_correctness_weight` | `0.0` (control) / `1.0` (treatment) |
| Steps per run | `600` |
| `grounded_input_fraction` | `0.67` |
| Pest evolution | frozen (`freeze_pest_evolution=True`) |

No subsidies, grace periods, juvenile discounts or population floors were added, and no
domain parameter was tuned for this measurement. TattleTots itself is untouched: `W`
reaches the engine only through `SimulationConfig`.

## Arms

Ordinary (evolved) arm is the thing under test; the designed arm is the ceiling
reference. Static-prior null is the domain's own, measured in the same runs.

| Metric | ordinary `W=0` | ordinary `W=1` | ordinary `W=0` holdout | ordinary `W=1` holdout | designed `W=0` | designed `W=1` |
|---|---|---|---|---|---|---|
| Seeds | 20 | 20 | 12 | 12 | 20 | 20 |
| Static-prior null | `0.6697` | `0.6697` | `0.6745` | `0.6745` | `0.6697` | `0.6697` |
| Realized precision | `0.1786` | `0.1731` | `0.1713` | `0.1696` | `0.6847` | `0.7113` |
| Margin vs null (pp) | `-49.11` | `-49.66` | `-50.32` | `-50.49` | `+1.50` | `+4.16` |
| Reports per adult lifetime | `317.2` | `336.8` | `309.2` | `302.9` | `64.7` | `57.7` |
| Silent-adult share | `0.0606` | `0.0493` | `0.0742` | `0.0690` | `0.3411` | `0.3421` |
| Cap-binding step share | `0.9801` | `0.9817` | `0.9796` | `0.9757` | `0.9469` | `0.9427` |
| Reproduction-eligible agent-step share | `0.9881` | `0.9891` | `0.9877` | `0.9861` | `0.9745` | `0.9728` |
| Generations observed | `4.9` | `4.3` | `4.8` | `4.6` | `8.3` | `8.7` |
| **Clause 1** mean slope / generation | `+0.00020` | `-0.00134` | `+0.00428` | `-0.01158` | `-0.03461` | `-0.01736` |
| **Clause 1** median slope | `-0.00264` | `+0.00404` | `+0.00299` | `-0.00438` | `-0.03628` | `-0.01676` |
| **Clause 1** seeds rising | `9/20` | `12/20` | `6/12` | `4/12` | `2/20` | `4/20` |
| **Clause 2** mean parent-child corr | `+0.0155` | `-0.0022` | `+0.0395` | `-0.0173` | `-0.0650` | `-0.1702` |
| **Clause 2** seeds above `0.2` | `1/20` | `0/20` | `1/12` | `0/12` | `0/20` | `0/20` |
| Pest-loop parent-child corr (positive control) | `+0.2733` | `+0.1906` | `+0.2155` | `+0.2011` | `+0.1632` | `+0.1774` |

## Per-seed, main block (seeds 1000-1019)

| Seed | slope W=0 | slope W=1 | corr W=0 | corr W=1 | precision W=0 | precision W=1 | cap W=0 | cap W=1 |
|---|---|---|---|---|---|---|---|---|
| 1000 | -0.00592 | -0.03649 | -0.0283 | +0.0205 | 0.1810 | 0.1781 | 0.992 | 0.988 |
| 1001 | +0.02628 | +0.01236 | -0.0605 | +0.0019 | 0.1894 | 0.1882 | 0.980 | 0.977 |
| 1002 | -0.00921 | +0.00452 | -0.1069 | -0.0553 | 0.1708 | 0.1528 | 0.988 | 0.985 |
| 1003 | -0.00402 | -0.00567 | +0.1363 | -0.0039 | 0.1590 | 0.1494 | 0.985 | 0.978 |
| 1004 | -0.00418 | +0.00468 | +0.1630 | -0.1142 | 0.1963 | 0.1952 | 0.990 | 0.992 |
| 1005 | +0.01161 | -0.00851 | +0.2544 | -0.0478 | 0.1657 | 0.1893 | 0.973 | 0.982 |
| 1006 | +0.01404 | +0.04811 | -0.0906 | +0.1416 | 0.1690 | 0.1534 | 0.933 | 0.982 |
| 1007 | +0.01369 | +0.01539 | +0.0243 | -0.1452 | 0.1979 | 0.1914 | 0.983 | 0.983 |
| 1008 | -0.00831 | +0.00613 | -0.0148 | -0.1112 | 0.1550 | 0.1659 | 0.988 | 0.988 |
| 1009 | -0.01156 | -0.00813 | +0.0499 | +0.0227 | 0.2096 | 0.1574 | 0.990 | 0.985 |
| 1010 | -0.00126 | +0.00460 | +0.1029 | +0.1742 | 0.1875 | 0.1762 | 0.990 | 0.988 |
| 1011 | +0.00209 | +0.00604 | -0.0914 | +0.0387 | 0.1769 | 0.1879 | 0.992 | 0.988 |
| 1012 | -0.00655 | +0.00206 | -0.0262 | +0.1031 | 0.1703 | 0.1644 | 0.983 | 0.985 |
| 1013 | -0.01795 | -0.00961 | -0.0749 | -0.1580 | 0.1757 | 0.1801 | 0.980 | 0.985 |
| 1014 | +0.00141 | -0.06096 | -0.1275 | +0.1101 | 0.1711 | 0.1911 | 0.972 | 0.983 |
| 1015 | -0.01381 | +0.00466 | +0.1317 | +0.0670 | 0.1795 | 0.1778 | 0.988 | 0.985 |
| 1016 | -0.00725 | -0.00835 | +0.1248 | -0.0772 | 0.1905 | 0.1585 | 0.980 | 0.980 |
| 1017 | +0.00214 | +0.00357 | +0.0175 | +0.0139 | 0.1959 | 0.1726 | 0.977 | 0.983 |
| 1018 | +0.00824 | +0.00459 | -0.2026 | +0.0484 | 0.1705 | 0.1593 | 0.948 | 0.932 |
| 1019 | +0.01463 | -0.00586 | +0.1300 | -0.0726 | 0.1726 | 0.1818 | 0.988 | 0.985 |

Slope range: `-0.01795..+0.02628` at `W=0`, `-0.06096..+0.04811` at `W=1` — the
treatment widens the spread in both directions rather than shifting it up.
Correlation range: `-0.2026..+0.2544` at `W=0`, `-0.1580..+0.1742` at `W=1`.

## Per-seed, holdout block (seeds 2000-2011)

| Seed | slope W=0 | slope W=1 | corr W=0 | corr W=1 | precision W=0 | precision W=1 | cap W=0 | cap W=1 |
|---|---|---|---|---|---|---|---|---|
| 2000 | -0.02235 | -0.01876 | +0.1370 | +0.1483 | 0.1795 | 0.1790 | 0.990 | 0.975 |
| 2001 | -0.01185 | -0.02865 | +0.0760 | -0.1078 | 0.1718 | 0.1940 | 0.983 | 0.983 |
| 2002 | -0.00537 | +0.01123 | -0.0839 | -0.0575 | 0.1665 | 0.1775 | 0.988 | 0.990 |
| 2003 | +0.02286 | -0.04642 | -0.0414 | -0.2183 | 0.1897 | 0.1832 | 0.983 | 0.980 |
| 2004 | +0.02205 | -0.00767 | -0.0027 | -0.0099 | 0.1839 | 0.1869 | 0.977 | 0.983 |
| 2005 | -0.00166 | -0.00501 | -0.0019 | -0.1596 | 0.1410 | 0.1254 | 0.978 | 0.978 |
| 2006 | -0.00745 | -0.04906 | -0.0209 | -0.0935 | 0.1551 | 0.1558 | 0.990 | 0.988 |
| 2007 | -0.00552 | -0.00036 | -0.0278 | +0.0501 | 0.1683 | 0.1588 | 0.987 | 0.985 |
| 2008 | +0.03369 | +0.00009 | -0.0811 | -0.0066 | 0.1497 | 0.1293 | 0.930 | 0.900 |
| 2009 | +0.00910 | +0.00052 | +0.0896 | +0.1669 | 0.1929 | 0.1780 | 0.977 | 0.978 |
| 2010 | +0.00763 | +0.00892 | +0.2419 | -0.0485 | 0.2072 | 0.1772 | 0.990 | 0.988 |
| 2011 | +0.01025 | -0.00375 | +0.1896 | +0.1283 | 0.1520 | 0.1795 | 0.982 | 0.978 |

## Verdict

- **Clause 1 — not met.** Rising-seed counts are 9/20 (`W=0`) versus 12/20 (`W=1`) in
  the main block and 6/12 versus 4/12 in the holdout: both blocks sit at coin-flip and
  the treatment moves in opposite directions across blocks. Mean slope is negative under
  `W=1` in both blocks. There is no within-run rise in the correct-report rate to
  attribute to the gate.
- **Clause 2 — not met.** Mean parent-child reproductive correlation is `+0.0155`
  (`W=0`) versus `-0.0022` (`W=1`), and only the control clears `0.2` on any seed
  (1/20 and 1/12, both plausibly noise given the `-0.20..+0.25` per-seed spread). The
  gate does not raise the correlation.
- **Not the SparseSensor mechanism.** On SparseSensor clause 2 was limited by a cap that
  bound on only ~1/3 of steps. Here the cap binds on `0.976..0.982` of steps with
  `0.986..0.989` of adult-steps eligible, so nearly every adult is competing for a
  rationed slot on nearly every step. That is the regime the gate was built for, and it
  still moves nothing: reproduction is rationed by rank, and with `~300+` reports per
  adult lifetime at `~0.17` precision, the correctness rank is close to a constant across
  agents, so re-keying merit on it barely reorders the queue.

## What is measured versus inferred

Measured directly: nulls, realized precision, per-seed clause-1 slopes and clause-2
correlations, rising/cleared seed counts, reports per adult lifetime, silent-adult
share, cap-binding and eligibility shares, generations observed, pest-loop
correlations — all from the engine's `PayoffLedger` over the runs above.

Inferred (mechanism, not measurement): the explanation that a near-constant correctness
rank is why the gate cannot reorder the queue. It is consistent with the high report
volume, near-uniform per-seed precision (`0.13..0.21`) and the near-saturated
eligibility share, but no per-agent rank-dispersion metric was recorded to confirm it.

Possible artifacts worth flagging:

- The designed-arm ceiling here (`0.6847` at `W=0`, `0.7113` at `W=1`, `+1.50` and
  `+4.16` pp) is far below the committed `0.8948` / `+33.37` pp. That committed number is
  a different configuration (400 steps, payoff levers off, `invasion` arm). The gate
  raises the designed arm's precision by `+2.66` pp, the only place any arm responds to
  `W` at all — but on that arm all reports come from a fixed hand-written policy, so the
  movement is population composition and escalation-threshold evolution, not agents
  learning to report better.
- Clause-1 slopes are fit over only `4.3..4.9` generations on the ordinary arms; the
  statistic is noisy by construction at this run length, which is why the rising-seed
  count and the per-seed spread are reported alongside the mean.
- Detector-side parent-child correlations are negative on several arms
  (`-0.045` ordinary `W=1`, `-0.170` designed `W=1`). A negative reproductive
  correlation under a hard cap is expected when offspring are rationed against parents,
  not evidence of anti-selection for correctness.

See `docs/designed_reporter_measurement.md` for the committed exploitable-margin
measurement this builds on.
