# Domain Modeling Master Plan: Avoiding Strawman Comparisons

## Core principle

The BMA/TattleTots architecture must be evaluated against competent, realistic alternatives, not toy baselines. Every competing architecture receives:

1. The same available sensors.
2. The same domain data streams.
3. The same operational budget class, unless explicitly testing cost constraints.
4. Reasonable modern ML/optimization methods.
5. Realistic phased deployment assumptions.

If centralized optimization wins under stable conditions, that is a real result. The expected BMA advantage is not magic accuracy. It is expected to appear under partial deployment, sensor churn, local heterogeneity, distribution drift, mixed adversarial dynamics, and attention constraints.

---

## Cross-domain architecture families to compare

### A0. Human/manual baseline
Humans scout, interpret, and respond with conventional tools. This is not a strawman: in agriculture and fire management, human scouting remains a serious baseline because humans carry local context and can operate under sparse instrumentation.

### A1. Current AI-enabled machinery
Modern commercial systems with embedded ML and automated execution.

Examples:
- Fire: camera network ML + human dispatch.
- Agriculture: AI tractors (e.g., See & Spray-like spot spraying), DJI/XAG-style prescription drones.
- Fisheries: AIS anomaly dashboards + human analysts.

### A2. Centralized multi-modal optimization platform
A high-end system using all available data streams, global state estimation, and centralized optimization.

Examples:
- Fire: OPIR + cameras + weather + fuels + drone fleet optimizer.
- Agriculture: satellite + drone + IoT + weather + prescription planning platform.
- Fisheries: AIS + SAR + catch reports + oceanography + stock model fusion.

This is the strongest conventional competitor.

### A3. Federated/edge intelligence
Local nodes run models and escalate anomalies upward. Strong where bandwidth or central connectivity is limited, but weaker for global optimization.

### A4. BMA / TattleTots ecology
Agents with dual-currency metabolism, emergent trophic roles, attention competition, reproduction/death, residual feeding, and domain-specific physical embodiment where appropriate.

---

# FireEcology v2: Fire-regime management with drone Tots

## Problem scope

Not just active wildfire detection. The simulation must include:

1. Hotspot and smoldering detection.
2. Dry fuel / dry spot monitoring.
3. Firebreak planning and maintenance prioritization.
4. Controlled burn planning, monitoring, and escape detection.
5. Autonomous small-fire suppression by drones.
6. Human response escalation when autonomous suppression is insufficient.
7. OPIR as an always-available parallel backstop, not a BMA-exclusive asset.

## Physical Tots

Drones are not external actuators. Drones can be Tots.

A drone-Tot genome includes:
- Body plan: 5 gal scout/strike, 40 gal strike, relay, camera-only scout, hybrid.
- Battery capacity and SWAP strategy.
- Water/payload capacity.
- Sensor suite.
- Patrol/loiter/suppress/report budget allocation.
- Target terrain/risk niche.
- Escalation threshold to other drones and humans.

## Expected emergent roles

- Scout drones: high endurance, low payload, information-rich sensing.
- Strike drones: high payload, low sensing, consume scout residuals.
- Relay drones: maintain communication paths, consume topology residuals.
- Broker drones/agents: translate drone ecology state into human-legible reports.
- Whistleblowers: audit false detections, malfunctioning scouts, or wasted suppression sorties.

## Strong comparator: centralized drone fleet optimizer

The centralized competitor receives:
- Same drone fleet.
- Same OPIR tasking.
- Same camera/weather/fuel streams.
- Global state estimator.
- Central dispatch optimizer, e.g. mixed-integer routing/assignment or receding-horizon MPC.
- Fire spread model (Rothermel/FARSITE-like simplified equivalent).
- Human alerting pipeline.

It should be expected to perform well under stable conditions and complete deployment.

## Phased deployment / colonization scenarios

Based on ALERTWildfire/ALERTCalifornia growth and sensor pilots:

- Phase 0, months 0-6: 5 drones, 3 cameras, 4 weather stations, OPIR backstop, 50 km² pilot.
- Phase 1, months 6-12: 15 drones, 8 cameras, expanded sector, first autonomous suppression attempts.
- Phase 2, months 12-18: 30 drones, 12 cameras, fuel-moisture stations, full sector operations.
- Phase 3, months 18-24: expand to second sector or adjust fleet composition based on learned performance.

Key comparison: centralized optimizer must reconfigure against each partial network; BMA colonizes incrementally.

## Fire falsification metrics

- Detection latency for active fires.
- Hotspot lead time.
- Dry spot prediction precision/recall.
- Controlled burn escape detection latency.
- Autonomous suppression success rate by fire age and size.
- Drone sortie cost and battery/water logistics.
- False dispatch rate.
- Human crew escalation rate.
- Damage cost.
- OPIR rescue rate: fraction of fires first caught by OPIR after local network missed them.
- Graceful degradation under drone/sensor failure.
- Colonization curve: capability vs deployment phase.

---

# GrainGuard v2: Precision agriculture with physical Tots

## Problem scope

Not just pest detection. The simulation must include:

1. Pest scouting and diagnosis.
2. Weed detection and spot treatment.
3. Disease/stress discrimination.
4. Spray/no-spray decisions under economic thresholds.
5. Biological control preservation.
6. Resistance evolution and pest behavioral shifts.
7. Multiple cropping systems: monoculture grain, orchard, intercropping.

## Physical Tots

Drones, ground robots, AI tractors, and trap-service robots can all be embodied Tots.

A farm-Tot genome includes:
- Body plan: scout drone, spray drone, AI tractor/boom sprayer, trap robot, diagnostic microdrone.
- Sensor suite: multispectral, RGB, thermal, trap imaging, weather, soil moisture.
- Treatment payload: pesticide, herbicide, biological control release, none.
- Patrol/scout/spray/report allocation.
- Crop/pest niche specialization.
- Economic threshold policy.

## Co-evolutionary pest dynamics

Pests and weeds are not passive.

They do not attack drones directly, but they respond through:
- Resistance evolution to pesticide/herbicide pressure.
- Behavioral/phenological escape: feeding at night, underside leaves, margins.
- Detection-bias evolution: damage patterns below NDVI threshold or hidden under canopy.
- Spatial refuge dynamics: field edges, cover crops, untreated strips.

Tots can adapt faster within-season; pests/weeds adapt across generations/seasons. The Tots may accidentally select for future adversaries.

## Scenario variants

### Grain monoculture
Simplest case. Large homogeneous fields, row crops, relatively clean signal. Strong centralized competitors should do well.

### Orchard
Each tree is a unit with its own microclimate, pest burden, canopy, and management history. Tree-level heterogeneity creates niches for local specialists. Strong case for BMA.

### Intercropping / polyculture
Multiple crop species with overlapping canopies and different pest complexes. Stress signals are species-specific and coupled through facilitation/competition. Hardest case for monolithic classifiers.

## Strong comparators

- Human scouting + threshold IPM.
- AI tractor spot-sprayer (See & Spray-like) with modern embedded ML.
- Prescription drone service: centralized map generation + autonomous flight execution.
- Centralized precision ag platform: satellite/drone/weather/IoT fusion with global spray optimization.

## Ag falsification metrics

- Yield protected.
- Total pesticide/herbicide volume.
- False spray area.
- Missed infestation area.
- Economic net return.
- Resistance allele frequency over seasons.
- Biological control preservation.
- Detection lead time by pest/weed type.
- Performance under orchard and intercropping complexity.

---

# ReefWatch v2: Fishery monitoring

## Problem scope

Mixed ecological + adversarial system:

- Fish stocks respond ecologically to harvest and environment.
- IUU vessels respond strategically to enforcement.
- Managers have multiple attention budgets and timescales.

## Tots

Mostly software/sensor-fusion Tots, not physical drones initially. Potential later physical embodiment: patrol vessels or autonomous surface vehicles.

Roles:
- AIS behavior agents.
- SAR/optical vessel-detection agents.
- Catch-report consistency agents.
- Oceanographic habitat agents.
- Stock assessment agents.
- Patrol recommendation brokers.
- Whistleblowers auditing falsified catch reports or AIS gaps.

## Strong comparators

- Human observer program.
- Electronic monitoring + human review.
- AIS anomaly detection dashboard.
- Centralized AIS+SAR+catch+oceanography fusion system.

## Fishery falsification metrics

- IUU detection rate.
- False boarding/inspection rate.
- Patrol cost.
- Catch underreporting detection.
- Stock assessment error.
- Quota-setting error.
- Long-term biomass relative to BMSY.
- Economic loss to IUU.

---

# Recommended build order

1. TattleTots calibration and engine maturation — current phase.
2. FireEcology with drone Tots and centralized optimizer comparator.
3. GrainGuard monoculture, then orchard, then intercropping.
4. ReefWatch after the H-D-W adversarial layer matures.

Fire remains the best first domain because the physical actuation loop (sensing → drone response → human escalation → OPIR backstop) is concrete and fast to simulate. GrainGuard is the best second domain because it forces the same architecture into a slower, co-evolutionary system with strong economic thresholds.
