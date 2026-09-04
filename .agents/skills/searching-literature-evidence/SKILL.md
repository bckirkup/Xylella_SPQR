---
name: searching-literature-evidence
description: Search the peer-reviewed literature with the Consensus MCP server to source a GrainGuard parameter — pest phenology, resistance genetics, behavioural escape, damage rates, trap and sensor detection, economic injury levels — including how a hit becomes a provenance comment with an evidence grade. Use whenever a biological or agronomic constant needs a citation, or when asked what the literature says about a mechanism. Pairs with the org-level consensus-literature-retrieval skill, which owns retrieval mechanics.
---

# Searching the Literature (Consensus MCP)

## Retrieval mechanics are in the org-level skill

Load `consensus-literature-retrieval` (`~/.agents/skills/`) before searching. It
owns the tool surface, `include_full_text_chunks: true` — which is mandatory and
returns Results, Methods and tables, including for paywalled articles — query
construction, filter behaviour, result handling, and recording which section of
the paper a number was read from.

This skill is the other half: what needs sourcing in [GrainGuard], and what a hit is
allowed to become here.

## Query construction

- Good: `Rhopalosiphum maidis intrinsic rate of increase constant temperature life table` (also: `aphid development time degree days generation`)

Quantities this repo needs sourced, and the words that find them:

- Phenology — `degree-day model`, `lower developmental threshold`,
  `generations per season`, `life table`, `constant temperature`.
- Population dynamics — `intrinsic rate of increase`, `carrying capacity`,
  `dispersal distance`, `mark-recapture`.
- Damage — `yield loss per aphid-day`, `defoliation`, `root injury rating`,
  `economic injury level`, `economic threshold`.
- Resistance — `baseline susceptibility`, `resistance allele frequency`,
  `selection coefficient`, `refuge`, `fitness cost`.
- Behavioural escape — `nocturnal feeding`, `within-plant distribution`,
  `leaf underside`, `field margin`, `edge effect`.
- Detection — `pheromone trap catch efficiency`, `sampling plan`,
  `UAV multispectral detection`, `sensitivity`, `detection limit`.

## Filter discipline

- `medical_mode=true` is useless here — it restricts to ~8M medical documents
  and will discard the entire agricultural entomology literature.

- `human=true`, `controlled`, `sample_size_min` and `study_types` describe
  clinical designs. A field trial with four replicated blocks is none of them
  and will be filtered out.

- `domain="agri,bio,env"` is the useful narrowing when a query drags in
  unrelated fields.

- Do **not** set `year_min`. The canonical degree-day and economic-injury work
  is decades old and has not been superseded.

## A rate is not a constant — capture its conditions

`src/grain_guard/environment/pest.py` currently declares generation time as a
bare integer:

```python
_GENERATION_TIME: dict[PestSpecies, int] = {
    PestSpecies.APHID: 14,
    PestSpecies.ROOTWORM: 365,
    PestSpecies.ARMYWORM: 30,
}
```

Insect development is temperature-driven, so 14 days is a measurement *at some
temperature*. When you source one of these, record the conditions with it:

```python
_GENERATION_TIME: dict[PestSpecies, int] = {
    # <Species>: egg-to-adult 14 d at 25 C constant-temperature life table
    # (lower threshold 6.2 C, 118 degree-days). <Author> et al. <year>,
    # <journal> (DOI: <doi>). Grade B: laboratory rearing standing in for the
    # field, and the model has no temperature to convert degree-days with.
    PestSpecies.APHID: 14,
```

State **what was measured**, **under what conditions**, the value with its
range, and author + year + journal + DOI. Then grade it:

- **A** — direct measurement of this quantity for this species in this setting.
- **B** — a congener, a laboratory measurement standing in for the field, or an
  analogous crop.
- **C** — inferred, estimated, or a declared assumption.

If no source exists, say so explicitly rather than inventing a plausible number.
A declared Grade C with a sensitivity sweep is honest; a fabricated citation is
not.

## Source the starting value, not the evolved one

`night_feeding`, `underside_preference` and `resistance_freq` are **initial
conditions of an evolving process** — the simulation moves them under detection
and management pressure. A literature value therefore belongs at the start of a
run, and is not comparable to whatever the run ends at.

Two consequences:

- Source the **baseline**: pre-treatment resistance allele frequency, feeding
  behaviour in an unmanaged population. Papers reporting behaviour or
  resistance in a heavily treated population have measured a *result* of the
  same process the model simulates; using it as the initial value double-counts
  the selection.
- Never source a value by comparing it to the model's evolved endpoint. That is
  fitting the input to the output.

## What this search must never be used for

Do not search for a value that makes an arm measurement come out right — a
designed-reporter result, a gradient arm, a precision or recall figure in
`docs/*_measurement.md`. Those measurements are only informative if the biology
underneath them was sourced independently; screening candidate papers by which
value helps turns a measurement of the architecture into a measurement of the
search.
