"""Tests for plate read inference handler."""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch


def test_preprocess_returns_correct_shape():
    from inference import preprocess_image
    # Simulate a 640x480 RGB image
    img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    result = preprocess_image(img)
    assert result.shape[0] == 1  # batch dim
    assert result.shape[2] == 640  # width
    assert result.shape[3] == 640  # height (padded/resized)


def test_postprocess_extracts_plate_text():
    from inference import decode_ctc_output
    # Simulate CTC output — known character indices
    # 0=blank, 1='A', 2='B', 3='C', 4='1', 5='2', 6='3', 7='4'
    # "ABC1234" = [1,2,3,4,5,6,7] with blanks between
    mock_output = np.array([[1,0,2,0,3,0,4,0,5,0,6,0,7]])
    charset = '_ABC1234'
    result = decode_ctc_output(mock_output, charset)
    assert result == 'ABC1234'
