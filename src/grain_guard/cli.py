"""CLI entry-point for GrainGuard simulation."""

from __future__ import annotations

import argparse
import json

from grain_guard.adapter.grain_adapter import GrainGuardAdapter
from grain_guard.environment.field import LandscapeType


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="GrainGuard: precision agriculture simulator")
    parser.add_argument("--steps", type=int, default=200, help="Number of simulation steps")
    parser.add_argument(
        "--landscape",
        type=str,
        default="monoculture",
        choices=["monoculture", "orchard", "intercrop"],
        help="Landscape type",
    )
    parser.add_argument("--rows", type=int, default=20, help="Field grid rows")
    parser.add_argument("--cols", type=int, default=20, help="Field grid cols")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--verbose", action="store_true", help="Print per-step status")
    parser.add_argument("--json", action="store_true", help="Output final metrics as JSON")
    args = parser.parse_args(argv)

    landscape = LandscapeType(args.landscape)
    adapter = GrainGuardAdapter(
        grid_rows=args.rows,
        grid_cols=args.cols,
        landscape=landscape,
        seed=args.seed,
    )

    for step in range(args.steps):
        adapter.step(step)
        ground_truth = adapter.get_ground_truth(step)
        if args.verbose and step % 20 == 0:
            field = adapter.field
            print(
                f"Step {step:4d} | "
                f"Health={field.mean_crop_health():.3f} | "
                f"Yield={field.mean_yield_potential():.3f} | "
                f"Pests={field.total_pest_density():.1f} | "
                f"Weeds={field.total_weed_density():.1f} | "
                f"Event={ground_truth}"
            )

    final = {
        "steps": args.steps,
        "landscape": args.landscape,
        "final_health": adapter.field.mean_crop_health(),
        "final_yield": adapter.field.mean_yield_potential(),
        "total_pests": adapter.field.total_pest_density(),
        "total_weeds": adapter.field.total_weed_density(),
    }

    if args.json:
        print(json.dumps(final, indent=2))
    else:
        print("\n--- Final State ---")
        for k, v in final.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
