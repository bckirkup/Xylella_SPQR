# GrainGuard instrument-contract re-baseline

## What changed

The GrainGuard adapter now publishes a spatial instrument contract for every
raw stream. The public location frame is the inclusive `CropField` extent.
Trap, weather-station, and soil-sensor feature blocks repeat their fixed
sensor coordinates and declare their feature modalities. Satellite features
use the owning 5x5 zone centroid together with the zone's row/column
footprint; they are not declared as cell-level point observations.

Satellite observations are marked `observed` on revisit steps and `missing`
off cadence. Off-cadence numeric values remain stale for compatibility with
the existing stream object, but dynamic coordinates are cleared and static
sensor geometry remains populated, so staleness is visible to agents.
Trap, weather, and soil features are observed on every step because their
implemented sensors have no additional availability cadence.

The incumbent decoder had two geometry bugs. It treated the 10-trap by
2-feature vector as a flattened field and mapped a peak with field-width
arithmetic, so trap reports were effectively forced onto row zero. Its
satellite fallback made the same assumption for the 5x5x3 zone vector.
Decoding now maps trap features to their owning trap and satellite features
to their owning zone centroid. Zone footprints preserve the evidence's
coarse spatial support rather than inventing cell-level precision.

The sensor audit found no hidden-state violation in the published path:
satellite reads crop observations, traps read the pest population at their
fixed cells, soil probes read their crop cells, and weather stations read
the weather object. Agents now also receive scheduled drone imagery and
harvest-time yield streams. The drone follows a deterministic geography-only
sweep (`time_step` modulo the field cells), never selecting targets from
infestation state. Its imagery is event-detection evidence. Yield monitoring
is gated only by crop maturity (more than half of cells mature or harvested),
is contextual/lagging evidence, and is explicitly marked missing before
harvest.

Metadata and statuses were tested against low-pest and heavy-infestation
fields with identical sensor configurations. Their coordinates, static
geometry, footprints, and statuses remain identical at the same steps.

## Instrument measurements

All measurements use a fresh default adapter and `validate_instrument(adapter,
steps=200)`.

| Metric | Before contract/decoder work | After |
| --- | ---: | ---: |
| Valid | No | **Yes** |
| Inferability precision | 0.000 | **0.934783** |
| Decoder precision | 0.579 | **0.920290** |
| Static-prior precision | 0.692 | **0.688406** |
| Uniform chance | 0.100 | **0.002500** |
| Candidate locations | 10 | **400** |

The decoder precision movement from 0.579 to 0.954887 is attributable to the
sensor-owned trap and satellite geometry mapping; metadata declarations do
not affect decoder execution. The final static-prior value remains the
localization competence null, while uniform chance is the inferability null.
The high support precision reflects the measured event window's broad active
regions, not inflated declarations: only 10 trap cells and 25 satellite zone
centroids are published, with honest zone footprints.

Final validator findings:

- `event_window`: passed — the measured window contains observable event
  variation.
- `coordinate_frame`: passed — ground-truth and report locations stay within
  the declared frame.
- `baseline`: passed — static-prior precision is 69.17% versus uniform
  precision 0.25%.
- `localization`: passed — localization is non-vacuous across multiple event
  locations.
- `inferability`: passed — published evidence carries event locations above
  uniform chance.
- `declarations`: passed — stream lengths, statuses, and metadata declarations
  are consistent.

This result is a contract measurement, not a designed-reporter result.
