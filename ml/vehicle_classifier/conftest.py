"""Conftest: ensure vehicle_classifier directory is on sys.path and inference module is correct."""
import os
import sys

import pytest

_here = os.path.dirname(__file__)


@pytest.fixture(autouse=True)
def use_vehicle_classifier_inference():
    """Ensure the vehicle_classifier inference module is used, not plate_read's."""
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
