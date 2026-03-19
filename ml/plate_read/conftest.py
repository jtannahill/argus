"""Conftest: ensure plate_read directory is on sys.path and inference module is correct."""
import os
import sys
import importlib

import pytest

_here = os.path.dirname(__file__)


@pytest.fixture(autouse=True)
def use_plate_read_inference():
    """Ensure the plate_read inference module is used, not vehicle_classifier's."""
    # Remove any cached 'inference' that points elsewhere
    if 'inference' in sys.modules:
        cached = sys.modules['inference'].__file__
        if not cached.startswith(_here):
            del sys.modules['inference']
    # Ensure our directory is first
    if _here in sys.path:
        sys.path.remove(_here)
    sys.path.insert(0, _here)
    yield
