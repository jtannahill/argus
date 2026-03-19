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
    # Simulate CTC output — known character indices in CHARSET
    # CHARSET = '_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    # A=1, B=2, C=3, 0=27, 1=28, 2=29, 3=30, 4=31
    # "ABC1234" = [1,2,3,28,29,30,31] with blanks between
    mock_output = np.array([[1,0,2,0,3,0,28,0,29,0,30,0,31]])
    charset = '_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    result = decode_ctc_output(mock_output, charset)
    assert result == 'ABC1234'
