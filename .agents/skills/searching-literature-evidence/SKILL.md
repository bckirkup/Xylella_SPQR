---
name: searching-literature-evidence
description: Search the peer-reviewed literature with the Consensus MCP server to source a GrainGuard parameter — pest phenology, resistance genetics, behavioural escape, damage rates, trap and sensor detection, economic injury levels — including query construction, filter discipline, and how a hit becomes a provenance comment with an evidence grade. Use whenever a biological or agronomic constant needs a citation, or when asked what the literature says about a mechanism.
---

# Searching the Literature (Consensus MCP)

The `consensus` MCP server has one tool, `search`, over ~220M papers
(Semantic Scholar, PubMed, Scopus, ArXiv). It returns title, authors, year,
journal, citation count, DOI, a Consensus URL, and the abstract.

```
mcp_tool(command="call_tool", server="consensus", tool_name="search",
         tool_args='{"query": "aphid development time degree days generation"}')
```

Run `mcp_tool(command="list_tools", server="consensus")` for the current
parameter list before using an unfamiliar filter.

## Query construction

Query in the vocabulary of the paper you want, not the question you have. In
entomology and agronomy the measured quantity is almost always named with its
conditions:

- Good: `Rhopalosiphum maidis intrinsic rate of increase constant temperature life table`
- Weak: `how fast do aphids reproduce`

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

Search for the mechanism, then separately for the number. Use scientific
binomials once you know which species stands behind `PestSpecies.APHID` in the
scenario you are sourcing — a genus-level query returns reviews, a binomial
query returns life tables.

## Filter discipline

Default to **no filters**; every filter silently removes evidence. Specific to
this repo:

- `medical_mode=true` is useless here — it restricts to ~8M medical documents
  and will discard the entire agricultural entomology literature.
- `human=true`, `controlled`, `sample_size_min` and `study_types` describe
  clinical designs. A field trial with four replicated blocks is none of them
  and will be filtered out.
- `domain="agri,bio,env"` is the useful narrowing when a query drags in
  unrelated fields.
- Do **not** set `year_min`. The canonical degree-day and economic-injury work
  is decades old and has not been superseded.
- `sjr_max=1` gives Q1 only; never reach for `sjr_min`, which *excludes* the top
  tiers, and would drop exactly the applied-entomology journals this repo needs.

Filters reorder as well as remove: the top hit for the same query changes when
`domain` and `year_min` are set. Re-run a promising query without filters before
calling any value *the* measurement.

## Result handling

- Default page returns 20 papers; `page_size` narrows it (5 works). `page=1`
  returns a genuinely different set on this organisation's plan, so paginate
  when the first page is all reviews.
- Twenty abstracts overflow the tool result. The output is truncated and the
  full text written to a file named in the truncation notice — **read that
  file**. Items 15-20 are frequently the measurement papers, because reviews
  rank higher.
- Life-table and yield-loss numbers usually live in a table, not the abstract.
  Open the DOI when the constant matters.
- Consensus asks for numbered inline citations with hyperlinked titles and the
  exact URLs it returned. Preserve the DOI when it gives one.

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

Fix the query and the filters from the definition of the quantity, before
looking at what the arm needs. If several papers measure it, take a stated
central value or the midpoint of the range and say which — not the end that
helps. If a sourced constant makes an arm look worse, that is a result: report
it.
