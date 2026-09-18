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


def make_cell(row, col, inlet, outlet):
    return {"row": row, "col": col, "inlet_temp": inlet, "outlet_temp": outlet}


def make_snapshot(inlet_base=25.0, outlet_base=30.0, num_cells=4):
    """Build one 1D 'snapshot' (flat list of ThermalCell dicts) for /thermos/predict."""
    return [
        make_cell(i, 0, inlet_base + i, outlet_base + i)
        for i in range(num_cells)
    ]
