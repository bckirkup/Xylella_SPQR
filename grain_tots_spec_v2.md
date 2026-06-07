# GrainTots / GrainGuard: Domain Specification
## Precision Pest and Weed Management with Physical Tots

### 1. Purpose

GrainTots tests whether a self-organizing drone/sensor ecology can manage crop pests and weeds more cost-effectively than centralized precision agriculture platforms or conventional IPM. The problem includes pest scouting, diagnosis, economic-threshold spray decisions, weed management, biological control preservation, and resistance management under co-evolutionary pest dynamics.

### 2. Core Hypothesis

A BMA drone ecology can reduce total cost (monitoring + treatment + crop loss + long-term resistance cost) compared to modern AI-enabled precision agriculture, by adapting to local heterogeneity, seasonal drift, and co-evolutionary pest response faster than centralized systems.

### 3. Environment

#### 3.1 Landscape Variants

Three cropping systems, escalating in complexity:

**Grain monoculture:** Large homogeneous fields (~10,000 ha), row crops (wheat, corn, soy). Relatively clean signal space. Strong centralized competitors should perform well here.

**Orchard:** Individual trees (~1,000 trees) with unique microclimates, canopies, and pest burdens. Tree-level heterogeneity creates niches for local specialists. Cover crop alleys provide beneficial insect habitat. Strong case for BMA.

**Intercropping / polyculture:** Multiple crop species with overlapping canopies and different pest complexes. Facilitation effects (nitrogen fixation, ground shading). Signal space is multi-dimensional in ways that challenge monolithic classifiers.

#### 3.2 Pest and Weed Dynamics

Pests and weeds are NOT passive. They respond to the management system through co-evolutionary dynamics:

- Resistance evolution: simple 1-locus model for pesticide/herbicide resistance allele, selected by treatment pressure.
- Behavioral escape: individuals that feed on detection-resistant surfaces (underside leaves, canopy-hidden), at detection-resistant times (night), or in spatial refugia (field margins, cover crop strips) are selected.
- Detection-bias evolution: damage patterns that remain below NDVI detection thresholds are selected for by systems relying on aerial spectral indices.
- Spatial dynamics: diffusion + wind-assisted dispersal + edge effects.
- Biological control agents: parasitoid wasps, lady beetles, ground beetles. Population dynamics coupled to pest density and pesticide disturbance.
- Pest generation time: aphids ~2 weeks, rootworm ~1 year, weeds ~1 season.

#### 3.3 Economics

EIL = C / (V · D · I · K), where:
- C = management cost per production unit
- V = market value per production unit
- D = damage per unit injury
- I = injury per pest
- K = proportional reduction from management action

Economic Threshold ≈ 0.75 × EIL.

These should emerge from selection pressure on the Tots, not be hardcoded.

### 4. Sensors and Basal Streams

#### 4.1 Satellite Multispectral
- NDVI, NDRE, chlorophyll indices per zone
- Resolution: 10-20 m (Sentinel-2-like) or 3 m (PlanetScope-like)
- Revisit: 3-5 days
- Detects crop stress but NOT pest-specific

#### 4.2 Drone Imagery
- High-resolution RGB + multispectral + thermal
- On-demand tasking (cost per flight)
- Can detect pest damage at leaf level
- Orchard: individual tree canopy imaging
- Intercrop: species-discriminated imaging

#### 4.3 Pheromone Traps
- Fixed network (sparse)
- Species-specific adult pest counts
- Direct pest detection but limited spatial coverage

#### 4.4 Weather Stations
- Temperature, humidity, wind, rain
- Drives degree-day pest phenology models

#### 4.5 Soil/Moisture Sensors
- IoT network in field
- Drives crop stress models (drought vs pest discrimination)

#### 4.6 Yield Monitor (Delayed)
- Available only at harvest
- Retrospective ground truth for seasonal pest impact

### 5. Physical Tot Body Plans

A farm-Tot genome encodes:
- Body type: scout drone, spray drone, AI tractor/boom sprayer, trap-service robot, diagnostic microdrone
- Sensor suite: multispectral, RGB, thermal, trap camera, weather, soil probe
- Treatment payload: pesticide, herbicide, biological control agent, none
- Patrol/scout/diagnose/spray/report energy allocation
- Crop and pest niche specialization
- Economic threshold behavior
- Spatial operating range

Expected emergent roles:
- Scout drones: fly transects, compress vegetation indices, produce residuals
- Diagnostic drones: consume scout residuals (anomalous patches), fly low, identify pest species
- Spray drones: consume diagnostic reports, apply targeted treatment at verified above-threshold locations
- Trap servicers: count insects, provide ground-truth calibration for aerial scouts; whistleblower function — audit whether stress signals actually correlate with pest presence
- AI tractors: operate in monoculture rows, spot-spray weeds; compete with scout/spray drones on efficiency

### 6. Users

#### Agronomist (Field-Level)
- High attention budget, daily decisions
- Priority: which zones to scout, when to spray
- Values economic threshold compliance

#### Farm Manager (Operation-Level)
- Weekly frequency, strategic
- Priority: total budget allocation, spray volume, resistance management
- Values long-term sustainability over single-season yield

### 7. Competing Architectures

#### A0 Human scouting + calendar/threshold IPM
Walk the field, count pests, spray on calendar or when count exceeds ET. Lowest technology, still dominant globally.

#### A1 AI-enabled tractor
John Deere See & Spray-class. Camera on tractor boom, real-time weed classification, spot-spray. Centralized model trained offline, deployed on-device. Strong for weeds in row crops, limited for canopy pests or 3D orchards.

#### A2 Prescription drone service
Autonomous spray drones with pre-planned flight paths. Prescription maps from satellite imagery + agronomist interpretation. Centralized planning, distributed execution. No real-time within-flight adaptation.

#### A3 Centralized precision ag platform
Climate Corp / Farmers Edge / Taranis class. Satellite + drone + IoT + weather fusion into a single decision engine. Global optimization of spray timing, rate, location. Retrained seasonally. Full strength conventional competitor.

#### A4 BMA / TattleTots ecology
Self-organizing drone/tractor/sensor ecology.

### 8. Deployment Scenario

- Season 1: 3 scout drones, 1 spray drone, 10 traps, 2 weather stations, satellite data. Monoculture pilot on 500 ha.
- Season 2: 10 scout, 3 spray, 1 AI tractor, 20 traps. Expand to 2,000 ha. First orchard trial.
- Season 3: full fleet. Add intercropping plots. Compare against centralized platform on same fields.

### 9. Metrics

- Yield protected (tonnes saved vs no-management baseline)
- Total pesticide/herbicide volume applied
- False spray area (treated but no actual pest/weed present)
- Missed infestation area (above ET but untreated)
- Economic net return
- Resistance allele frequency trajectory over seasons
- Beneficial insect population (biological control preservation)
- Detection lead time by pest/weed type
- Cost per hectare (monitoring + treatment + crop loss)
- Performance degradation from monoculture → orchard → intercrop

### 10. Falsification Test

BMA must achieve equal or better yield protection with less total pesticide input AND slower resistance evolution, compared to the centralized precision ag platform receiving the same sensor data. If centralized beats BMA in monoculture, that's a real result — BMA's advantage should appear in orchard and intercropping where local heterogeneity is highest.
