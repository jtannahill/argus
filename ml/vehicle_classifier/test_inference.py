"""Tests for vehicle classifier inference."""

import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))


def test_preprocess_returns_correct_shape():
    from inference import preprocess_image
    img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    result = preprocess_image(img)
    assert result.shape == (1, 3, 300, 300)


def test_decode_predictions_returns_all_fields():
    from inference import decode_predictions
    # Mock softmax outputs for 4 heads
    mock_outputs = {
        'make': np.array([[0.1, 0.8, 0.1]]),
        'model': np.array([[0.7, 0.2, 0.1]]),
        'year': np.array([[0.0, 0.0, 0.9, 0.1]]),
        'color': np.array([[0.1, 0.1, 0.8]]),
    }
    labels = {
        'make': ['Toyota', 'Honda', 'Ford'],
        'model': ['Camry', 'Civic', 'F150'],
        'year': ['2020', '2021', '2022', '2023'],
        'color': ['White', 'Black', 'Silver'],
    }
    result = decode_predictions(mock_outputs, labels)
    assert result['make'] == 'Honda'
    assert result['year'] == '2022'
    assert result['color'] == 'Silver'
