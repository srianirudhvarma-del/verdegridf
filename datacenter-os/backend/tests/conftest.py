import sys
from pathlib import Path

# Ensure `backend/` (the parent of this tests/ dir) is importable as the
# project root, matching how main.py does `from api.routes import router`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture()
def client():
    return TestClient(app)


def make_cell(cell_id, x, y, inlet, outlet):
    return {"id": cell_id, "x": x, "y": y, "inlet_celsius": inlet, "outlet_celsius": outlet}


def make_snapshot(inlet_base=25.0, outlet_base=30.0, num_cells=4):
    """Build one 1D 'snapshot' (flat list of ThermalCell dicts) for /thermaltrace/predict."""
    return [
        make_cell(f"cell_{i}", i, 0, inlet_base + i, outlet_base + i)
        for i in range(num_cells)
    ]
