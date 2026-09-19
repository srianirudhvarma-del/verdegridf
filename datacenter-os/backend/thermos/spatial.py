"""
thermos/spatial.py -- SHOULD HAVE #23: grid-shaped spatial modeling +
explicit sensor-vs-interpolated flagging.

SCOPE NOTE: the methodology calls for real ConvLSTM2D layers learning
spatial correlations from training data. This project has no deep-learning
framework in its dependencies (backend/requirements.txt: fastapi,
pydantic, numpy, uvicorn, httpx only) and no real historical grid data to
train on -- building and training an actual ConvLSTM is out of reach here
without adding a new heavy dependency (torch/tensorflow) and a real
training pipeline. That would need a separate go-ahead, not something to
add silently as a side effect of this item.

What's implemented instead -- the two concretely buildable pieces:
  1. SpatialResidualCorrector: a genuine (height, width)-shaped per-cell
     residual structure, replacing model.py's ResidualCorrector's flat
     whole-rack scalar, with a lightweight deterministic
     spatial-neighbor-averaging correction (not a trained neural net --
     an explicit stand-in, same spirit as the physics-lite core needing
     zero training data before model.py's residual corrector).
  2. interpolate_grid: explicit sensor-vs-interpolated flagging, using
     inverse-distance weighting (a lightweight, documented substitute for
     Kriging) to fill missing cells -- so the UI/data model never lets
     interpolated values look identical to real sensor readings.
"""

import math
import statistics
from dataclasses import dataclass
from typing import Optional


@dataclass
class GridCellReading:
    x: int
    y: int
    value: Optional[float]  # None == missing, needs interpolation


@dataclass
class InterpolatedGrid:
    values: list[list[float]]
    isInterpolated: list[list[bool]]


def interpolate_grid(readings: list[GridCellReading], width: int, height: int, *, power: float = 2.0) -> InterpolatedGrid:
    """
    Inverse-distance-weighted interpolation for missing cells. Real
    sensor cells are copied through untouched and flagged
    isInterpolated=False; only missing cells are filled and flagged True.
    """
    known: dict[tuple[int, int], float] = {(r.x, r.y): r.value for r in readings if r.value is not None}
    if not known:
        raise ValueError("need at least one real sensor reading to interpolate from")

    values = [[0.0] * width for _ in range(height)]
    is_interpolated = [[False] * width for _ in range(height)]

    for y in range(height):
        for x in range(width):
            known_value = known.get((x, y))
            if known_value is not None:
                values[y][x] = known_value
                continue

            weighted_sum = 0.0
            weight_total = 0.0
            exact_match: Optional[float] = None
            for (kx, ky), kv in known.items():
                distance = math.hypot(kx - x, ky - y)
                if distance == 0:
                    exact_match = kv
                    break
                weight = 1.0 / (distance ** power)
                weighted_sum += weight * kv
                weight_total += weight

            values[y][x] = exact_match if exact_match is not None else weighted_sum / weight_total
            is_interpolated[y][x] = True

    return InterpolatedGrid(values=values, isInterpolated=is_interpolated)


class SpatialResidualCorrector:
    """
    Grid-shaped (not flat/scalar) residual correction: maintains a
    per-cell rolling residual history and blends each cell's own
    historical mean with its immediate neighbors' -- deterministic
    spatial smoothing, not a learned/trained correlation. This is the
    honest, buildable stand-in for ConvLSTM2D described in the module
    docstring above.
    """

    def __init__(self, width: int, height: int, *, window: int = 30) -> None:
        self.width = width
        self.height = height
        self.window = window
        self._history: dict[tuple[int, int], list[float]] = {}

    def record_residual(self, x: int, y: int, residual: float) -> None:
        history = self._history.setdefault((x, y), [])
        history.append(residual)
        if len(history) > self.window:
            history.pop(0)

    def predict_residual_grid(self) -> list[list[float]]:
        own_mean = {cell: statistics.mean(hist) for cell, hist in self._history.items() if hist}
        grid = [[0.0] * self.width for _ in range(self.height)]

        for y in range(self.height):
            for x in range(self.width):
                own_value = own_mean.get((x, y), 0.0)
                neighbor_values = [
                    own_mean[neighbor] for neighbor in self._neighbors(x, y) if neighbor in own_mean
                ]
                neighbor_avg = statistics.mean(neighbor_values) if neighbor_values else own_value
                grid[y][x] = 0.5 * own_value + 0.5 * neighbor_avg

        return grid

    @staticmethod
    def _neighbors(x: int, y: int):
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            yield (x + dx, y + dy)
