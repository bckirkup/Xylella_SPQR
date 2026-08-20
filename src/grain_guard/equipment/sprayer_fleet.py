"""Finite per-Tot spray capacity: tanks, doses, and refill trips.

Scarcity in this domain is a property of the equipment, not of an accountant.
Each sprayer Tot is a physical machine with a fixed body plan: a tank of a given
volume, a top speed, and a treatment payload. Every targeted application draws a
dose from that tank, and an empty tank sends the Tot on a refill trip that costs
travel time to the refill point plus a fixed refill duration. While it is
travelling or refilling it cannot treat anything, so an application spent on a
false positive is an application unavailable for a true one nearby.

Two operations are distinguished because real equipment distinguishes them:

* a *spot* application treats one cell and is served by the spray-drone fleet,
  which is what COP dispatch and any detector-driven policy uses;
* a *broadcast* pass treats many cells in one operation and is served by the
  boom-sprayer tractor, which carries an order of magnitude more volume.

Only spot capacity is scarce. The boom sprayer refills from a nurse tank at the
headland, so a whole-field pass is never refused and total pesticide load is not
capped: a manager who wants to treat everything can still do so, which is what
keeps over-spraying ecologically self-defeating instead of throttling it into
harmlessness the way a global volume quota does. ``broadcast_headland_refill``
turns that off for anyone who wants to measure the capped variant.

Body plans are fixed hardware here, as everywhere else in this domain: the
config chooses how many machines of which plan the farm owns and how much
product an application consumes, never how the hardware behaves mid-run.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, model_validator

from grain_guard.equipment.body_plan import BodyPlan

DEFAULT_SPOT_SPRAYERS = 8
"""Spray drones the farm owns by default."""

DEFAULT_APPLICATIONS_PER_STEP = 4
"""Cells one loaded drone can treat within a single step."""

DEFAULT_LITERS_PER_APPLICATION = 2.0
"""Product a single spot application consumes."""

DEFAULT_REFILL_DURATION_STEPS = 2
"""Steps spent at the refill point once a sprayer arrives there."""

DEFAULT_LITERS_PER_BROADCAST_CELL = 0.5
"""Product a boom pass consumes per treated cell."""

DEFAULT_BROADCAST_CELLS_PER_STEP = 400
"""Cells one boom pass can cover in a single step."""


class SprayerFleetConfig(BaseModel):
    """Farm-owned spray equipment and what an application costs it.

    Attributes:
        n_spot_sprayers: spray drones available for targeted applications.
        spot_tank_liters: tank volume per drone; ``None`` uses the spray-drone
            body plan's own capacity.
        liters_per_application: product one targeted application consumes.
        applications_per_step: cells one loaded drone treats within a step; the
            tank, not this rate, is meant to be the binding constraint.
        refill_row: row of the refill point; ``None`` puts it mid-field.
        refill_col: column of the refill point; ``None`` puts it mid-field.
        refill_duration_steps: steps spent refilling after arriving.
        broadcast_enabled: whether the farm owns a boom sprayer at all.
        broadcast_headland_refill: refill the boom from a nurse tank at the
            headland, so broadcast volume costs product but no downtime and a
            pass is never refused. ``False`` sends the boom on the same refill
            trips the drones make, which caps field-wide pesticide load.
        broadcast_tank_liters: boom-sprayer tank; ``None`` uses the AI-tractor
            body plan's own capacity.
        liters_per_broadcast_cell: product a boom pass consumes per cell.
        broadcast_cells_per_step: cells one boom pass covers in one step.
    """

    n_spot_sprayers: int = Field(default=DEFAULT_SPOT_SPRAYERS, ge=1)
    spot_tank_liters: float | None = Field(default=None, gt=0.0)
    liters_per_application: float = Field(default=DEFAULT_LITERS_PER_APPLICATION, gt=0.0)
    applications_per_step: int = Field(default=DEFAULT_APPLICATIONS_PER_STEP, ge=1)
    refill_row: int | None = Field(default=None, ge=0)
    refill_col: int | None = Field(default=None, ge=0)
    refill_duration_steps: int = Field(default=DEFAULT_REFILL_DURATION_STEPS, ge=0)
    broadcast_enabled: bool = Field(default=True)
    broadcast_headland_refill: bool = Field(default=True)
    broadcast_tank_liters: float | None = Field(default=None, gt=0.0)
    liters_per_broadcast_cell: float = Field(default=DEFAULT_LITERS_PER_BROADCAST_CELL, gt=0.0)
    broadcast_cells_per_step: int = Field(default=DEFAULT_BROADCAST_CELLS_PER_STEP, ge=1)

    @property
    def resolved_spot_tank_liters(self) -> float:
        """Spot tank volume, defaulting to the spray-drone body plan."""
        if self.spot_tank_liters is not None:
            return self.spot_tank_liters
        return BodyPlan.spray_drone().tank_liters

    @property
    def resolved_broadcast_tank_liters(self) -> float:
        """Boom tank volume, defaulting to the AI-tractor body plan."""
        if self.broadcast_tank_liters is not None:
            return self.broadcast_tank_liters
        return BodyPlan.ai_tractor().tank_liters

    @model_validator(mode="after")
    def _doses_must_fit_their_tanks(self) -> SprayerFleetConfig:
        """A dose larger than the tank would make every request impossible."""
        if self.liters_per_application > self.resolved_spot_tank_liters:
            raise ValueError("liters_per_application exceeds the spot sprayer tank volume")
        if self.broadcast_enabled and (
            self.liters_per_broadcast_cell > self.resolved_broadcast_tank_liters
        ):
            raise ValueError("liters_per_broadcast_cell exceeds the boom sprayer tank volume")
        return self


@dataclass
class SprayerTot:
    """One physical sprayer: fixed hardware, mutable position and tank level.

    Attributes:
        body_plan: fixed hardware template.
        row: current row on the field grid.
        col: current column on the field grid.
        tank_capacity: full tank volume.
        tank_remaining: product left in the tank.
        available_at_step: first step at which this Tot can treat again.
        service_step: step its within-step application count refers to.
        served_this_step: applications it has already made this step.
        applications: applications it has made.
        refills: refill trips it has made.
        cells_travelled: Chebyshev cells it has moved.
        liters_applied: product it has applied.
    """

    body_plan: BodyPlan
    row: int
    col: int
    tank_capacity: float
    tank_remaining: float
    available_at_step: int = 0
    service_step: int = -1
    served_this_step: int = 0
    applications: int = 0
    refills: int = 0
    cells_travelled: float = 0.0
    liters_applied: float = 0.0

    def is_on_field(self, step: int) -> bool:
        """Whether this Tot is on the field rather than away refilling."""
        return self.available_at_step <= step

    def has_work_left(self, step: int, applications_per_step: int) -> bool:
        """Whether this Tot's working beat for the step still has room."""
        return self.service_step != step or self.served_this_step < applications_per_step

    def is_loaded(self, dose: float) -> bool:
        """Whether the tank still holds one application."""
        return self.tank_remaining >= dose

    def record_application(self, step: int) -> None:
        """Count one application against this step's work."""
        if self.service_step != step:
            self.service_step = step
            self.served_this_step = 0
        self.served_this_step += 1
        self.applications += 1

    def travel_steps(self, row: int, col: int) -> int:
        """Steps this Tot needs to reach a cell at its own top speed."""
        distance = float(max(abs(row - self.row), abs(col - self.col)))
        return int(math.ceil(distance / self.body_plan.max_speed))

    def move_to(self, row: int, col: int) -> None:
        """Fly to a cell, accumulating the distance covered."""
        self.cells_travelled += float(max(abs(row - self.row), abs(col - self.col)))
        self.row = row
        self.col = col


@dataclass
class FleetCounters:
    """Fulfillment accounting for one fleet.

    Attributes:
        granted: applications the fleet served.
        denied_empty: requests refused because every working Tot needed product.
        denied_refilling: requests refused because every Tot was away refilling.
        denied_worked_out: requests refused because every Tot on the field had
            already flown its full beat for that step.
        refills: refill trips started.
        liters_applied: product applied.
        broadcast_passes: boom passes started.
        broadcast_cells: cells a boom pass treated.
        broadcast_cells_denied: broadcast cells the boom could not reach.
    """

    granted: int = 0
    denied_empty: int = 0
    denied_refilling: int = 0
    denied_worked_out: int = 0
    refills: int = 0
    liters_applied: float = 0.0
    broadcast_passes: int = 0
    broadcast_cells: int = 0
    broadcast_cells_denied: int = 0


@dataclass
class SprayerFleet:
    """The farm's spray equipment and its per-step availability.

    Attributes:
        config: equipment the farm owns and what an application costs.
        rows: field rows, used to place the fleet.
        cols: field columns, used to place the fleet.
    """

    config: SprayerFleetConfig
    rows: int
    cols: int
    spot_sprayers: list[SprayerTot] = field(default_factory=list)
    boom_sprayer: SprayerTot | None = None
    counters: FleetCounters = field(default_factory=FleetCounters)

    def __post_init__(self) -> None:
        self.spot_sprayers = [
            self._build_spot_sprayer(index) for index in range(self.config.n_spot_sprayers)
        ]
        self.boom_sprayer = self._build_boom_sprayer() if self.config.broadcast_enabled else None

    def _build_spot_sprayer(self, index: int) -> SprayerTot:
        """Place one drone on its own row band, hangared at mid-field column."""
        plan = BodyPlan.spray_drone()
        capacity = self.config.resolved_spot_tank_liters
        row = int((index + 1) * self.rows / (self.config.n_spot_sprayers + 1))
        return SprayerTot(
            body_plan=plan,
            row=min(row, self.rows - 1),
            col=self.cols // 2,
            tank_capacity=capacity,
            tank_remaining=capacity,
        )

    def _build_boom_sprayer(self) -> SprayerTot:
        capacity = self.config.resolved_broadcast_tank_liters
        return SprayerTot(
            body_plan=BodyPlan.ai_tractor(),
            row=self._refill_row(),
            col=self._refill_col(),
            tank_capacity=capacity,
            tank_remaining=capacity,
        )

    def _refill_row(self) -> int:
        if self.config.refill_row is None:
            return self.rows // 2
        return min(self.config.refill_row, self.rows - 1)

    def _refill_col(self) -> int:
        if self.config.refill_col is None:
            return self.cols // 2
        return min(self.config.refill_col, self.cols - 1)

    def _start_refill(self, sprayer: SprayerTot, step: int) -> None:
        """Send a Tot to the refill point and hold it there for the refill."""
        travel = sprayer.travel_steps(self._refill_row(), self._refill_col())
        sprayer.move_to(self._refill_row(), self._refill_col())
        sprayer.available_at_step = step + travel + self.config.refill_duration_steps
        sprayer.tank_remaining = sprayer.tank_capacity
        sprayer.refills += 1
        self.counters.refills += 1

    def request_spot_application(self, row: int, col: int, step: int) -> bool:
        """Assign the nearest free, loaded drone to treat one cell.

        Ties are broken by fleet index so the assignment is deterministic. A
        drone with too little product to serve the request leaves for a refill
        instead, and the request itself is refused: the tank is the constraint
        that is meant to bind, and the refill trip is what it costs.
        """
        dose = self.config.liters_per_application
        rate = self.config.applications_per_step
        on_field = [sprayer for sprayer in self.spot_sprayers if sprayer.is_on_field(step)]
        if not on_field:
            self.counters.denied_refilling += 1
            return False
        working = [sprayer for sprayer in on_field if sprayer.has_work_left(step, rate)]
        if not working:
            self.counters.denied_worked_out += 1
            return False
        loaded = [sprayer for sprayer in working if sprayer.is_loaded(dose)]
        if not loaded:
            for sprayer in working:
                self._start_refill(sprayer, step)
            self.counters.denied_empty += 1
            return False
        return self._serve_spot_request(loaded, row, col, step)

    def _serve_spot_request(self, loaded: list[SprayerTot], row: int, col: int, step: int) -> bool:
        """Fly the nearest loaded drone to a cell and draw its dose.

        Flight inside the field is part of a drone's working beat and is
        accounted in distance rather than charged as downtime; leaving the field
        to refill is what costs time.
        """
        dose = self.config.liters_per_application
        chosen = min(
            enumerate(loaded),
            key=lambda item: (item[1].travel_steps(row, col), item[0]),
        )[1]
        chosen.move_to(row, col)
        chosen.tank_remaining -= dose
        chosen.liters_applied += dose
        chosen.record_application(step)
        self.counters.granted += 1
        self.counters.liters_applied += self.config.liters_per_application
        return True

    def request_broadcast_pass(
        self, cells: Sequence[tuple[int, int]], step: int
    ) -> list[tuple[int, int]]:
        """Serve as much of a whole-field pass as the boom sprayer can.

        The boom carries far more product than a drone and tops up at the
        headland, so a pass is served in full; only one pass runs per step.
        """
        boom = self.boom_sprayer
        if boom is None or boom.available_at_step > step or not cells:
            self.counters.broadcast_cells_denied += len(cells)
            return []
        self.counters.broadcast_passes += 1
        served = self._serve_broadcast_cells(boom, cells, step)
        boom.available_at_step = max(boom.available_at_step, step + 1)
        self.counters.broadcast_cells += len(served)
        self.counters.broadcast_cells_denied += len(cells) - len(served)
        return served

    def _serve_broadcast_cells(
        self, boom: SprayerTot, cells: Sequence[tuple[int, int]], step: int
    ) -> list[tuple[int, int]]:
        """Cells one pass covers before the boom runs out of product or reach.

        With headland refilling the boom tops up in place: the refill is counted
        and the product is charged, but the pass continues, so broadcast volume
        is never the binding constraint.
        """
        dose = self.config.liters_per_broadcast_cell
        served: list[tuple[int, int]] = []
        for row, col in cells[: self.config.broadcast_cells_per_step]:
            if boom.tank_remaining < dose and not self._refill_boom_in_place(boom, step):
                break
            boom.tank_remaining -= dose
            boom.liters_applied += dose
            boom.applications += 1
            self.counters.liters_applied += dose
            served.append((row, col))
        if served:
            boom.move_to(*served[-1])
        return served

    def _refill_boom_in_place(self, boom: SprayerTot, step: int) -> bool:
        """Top the boom up at the headland, or send it away and end the pass."""
        if not self.config.broadcast_headland_refill:
            self._start_refill(boom, step)
            return False
        boom.tank_remaining = boom.tank_capacity
        boom.refills += 1
        self.counters.refills += 1
        return True

    def metrics(self) -> dict[str, float | int]:
        """Fleet-level fulfillment, downtime, and tank state."""
        spot_requests = (
            self.counters.granted
            + self.counters.denied_empty
            + self.counters.denied_refilling
            + self.counters.denied_worked_out
        )
        tank_shares = [
            sprayer.tank_remaining / sprayer.tank_capacity for sprayer in self.spot_sprayers
        ]
        return {
            "n_spot_sprayers": len(self.spot_sprayers),
            "spot_tank_liters": self.config.resolved_spot_tank_liters,
            "liters_per_application": self.config.liters_per_application,
            "applications_per_step": self.config.applications_per_step,
            "spot_requests": spot_requests,
            "spot_granted": self.counters.granted,
            "spot_denied_empty": self.counters.denied_empty,
            "spot_denied_refilling": self.counters.denied_refilling,
            "spot_denied_worked_out": self.counters.denied_worked_out,
            "spot_fulfilled_share": (
                self.counters.granted / spot_requests if spot_requests else 0.0
            ),
            "refills": self.counters.refills,
            "liters_applied": self.counters.liters_applied,
            "cells_travelled": sum(sprayer.cells_travelled for sprayer in self.spot_sprayers),
            "final_mean_tank_share": (sum(tank_shares) / len(tank_shares) if tank_shares else 0.0),
            "broadcast_passes": self.counters.broadcast_passes,
            "broadcast_cells": self.counters.broadcast_cells,
            "broadcast_cells_denied": self.counters.broadcast_cells_denied,
        }
