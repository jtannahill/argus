"""Tests for CLIP embedding inference handler.

torch and clip are not installed in the local dev environment (SageMaker-only).
All tests mock those imports via sys.modules before importing inference functions.
"""

import io
import json
import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))

# ---------------------------------------------------------------------------
# Stub out torch and clip in sys.modules before any inference import so that
# the lazy `import torch` / `import clip` inside the functions hit our mocks.
# ---------------------------------------------------------------------------

_mock_torch = MagicMock()
_mock_clip = MagicMock()

# torch.no_grad() must work as a context manager
_mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
_mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=False)

sys.modules.setdefault('torch', _mock_torch)
sys.modules.setdefault('clip', _mock_clip)
sys.modules.setdefault('numpy', np)       # real numpy is installed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jpeg_bytes(width: int = 224, height: int = 224) -> bytes:
    """Create minimal JPEG bytes for a solid-color image."""
    img = Image.fromarray(
        np.zeros((height, width, 3), dtype=np.uint8), mode="RGB"
    )
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_png_bytes(width: int = 100, height: int = 100) -> bytes:
    img = Image.fromarray(
        np.full((height, width, 3), 128, dtype=np.uint8), mode="RGB"
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# model_fn
# ---------------------------------------------------------------------------

def test_model_fn_returns_required_keys():
    # Reset the module so we get a fresh import with our sys.modules stubs
    sys.modules.pop('inference', None)
    from inference import model_fn

    mock_model = MagicMock()
    mock_preprocess = MagicMock()
    _mock_torch.cuda.is_available.return_value = False
    _mock_clip.load.return_value = (mock_model, mock_preprocess)

    result = model_fn("/tmp/model")

    _mock_clip.load.assert_called_with(
        "ViT-B/32", device="cpu", download_root="/tmp/model"
    )
    assert set(result.keys()) == {"model", "preprocess", "device"}
    assert result["device"] == "cpu"
    mock_model.eval.assert_called_once()


def test_model_fn_uses_cuda_when_available():
    sys.modules.pop('inference', None)
    from inference import model_fn

    mock_model = MagicMock()
    mock_preprocess = MagicMock()
    _mock_torch.cuda.is_available.return_value = True
    _mock_clip.load.return_value = (mock_model, mock_preprocess)

    result = model_fn("/tmp/model")

    _mock_clip.load.assert_called_with(
        "ViT-B/32", device="cuda", download_root="/tmp/model"
    )
    assert result["device"] == "cuda"


# ---------------------------------------------------------------------------
# input_fn
# ---------------------------------------------------------------------------

def test_input_fn_accepts_jpeg():
    sys.modules.pop('inference', None)
    from inference import input_fn

    jpeg_bytes = _make_jpeg_bytes()
    result = input_fn(jpeg_bytes, "image/jpeg")

    assert isinstance(result, Image.Image)
    assert result.mode == "RGB"


def test_input_fn_accepts_png():
    sys.modules.pop('inference', None)
    from inference import input_fn

    png_bytes = _make_png_bytes()
    result = input_fn(png_bytes, "image/png")

    assert isinstance(result, Image.Image)
    assert result.mode == "RGB"


def test_input_fn_accepts_octet_stream():
    sys.modules.pop('inference', None)
    from inference import input_fn

    jpeg_bytes = _make_jpeg_bytes()
    result = input_fn(jpeg_bytes, "application/octet-stream")

    assert isinstance(result, Image.Image)


def test_input_fn_rejects_unsupported_content_type():
    sys.modules.pop('inference', None)
    from inference import input_fn

    with pytest.raises(ValueError, match="Unsupported content type"):
        input_fn(b"data", "text/plain")


# ---------------------------------------------------------------------------
# predict_fn
# ---------------------------------------------------------------------------

def test_predict_fn_returns_512_dim_numpy_array():
    sys.modules.pop('inference', None)
    from inference import predict_fn

    # Build a real 512-dim tensor using numpy (torch is mocked)
    raw = np.random.randn(1, 512).astype(np.float32)

    # encode_image returns a mock that behaves like a real tensor for norm/div
    # We use a real numpy array wrapped in a mock to make the math work.
    class FakeTensor:
        def __init__(self, arr):
            self._arr = arr

        def norm(self, dim=-1, keepdim=False):
            n = np.linalg.norm(self._arr, axis=dim, keepdims=keepdim)
            return FakeTensor(n)

        def __truediv__(self, other):
            return FakeTensor(self._arr / other._arr)

        def squeeze(self, dim):
            return FakeTensor(self._arr.squeeze(dim))

        def cpu(self):
            return self

        def numpy(self):
            return self._arr.squeeze()

    fake_emb = FakeTensor(raw)

    mock_model = MagicMock()
    mock_model.encode_image.return_value = fake_emb

    mock_tensor = MagicMock()
    mock_tensor.unsqueeze.return_value = MagicMock(
        to=MagicMock(return_value=MagicMock())
    )
    mock_preprocess = MagicMock(return_value=mock_tensor)

    model_dict = {"model": mock_model, "preprocess": mock_preprocess, "device": "cpu"}
    dummy_image = Image.fromarray(np.zeros((224, 224, 3), dtype=np.uint8), mode="RGB")

    result = predict_fn(dummy_image, model_dict)

    assert isinstance(result, np.ndarray)
    assert result.shape == (512,)


def test_predict_fn_returns_normalized_embedding():
    """Verify the output is L2-normalized (unit vector)."""
    sys.modules.pop('inference', None)
    from inference import predict_fn

    raw = np.random.randn(1, 512).astype(np.float32)

    class FakeTensor:
        def __init__(self, arr):
            self._arr = arr

        def norm(self, dim=-1, keepdim=False):
            n = np.linalg.norm(self._arr, axis=dim, keepdims=keepdim)
            return FakeTensor(n)

        def __truediv__(self, other):
            return FakeTensor(self._arr / other._arr)

        def squeeze(self, dim):
            return FakeTensor(self._arr.squeeze(dim))

        def cpu(self):
            return self

        def numpy(self):
            return self._arr.squeeze()

    fake_emb = FakeTensor(raw)

    mock_model = MagicMock()
    mock_model.encode_image.return_value = fake_emb

    mock_tensor = MagicMock()
    mock_tensor.unsqueeze.return_value = MagicMock(
        to=MagicMock(return_value=MagicMock())
    )
    mock_preprocess = MagicMock(return_value=mock_tensor)

    model_dict = {"model": mock_model, "preprocess": mock_preprocess, "device": "cpu"}
    dummy_image = Image.fromarray(np.zeros((224, 224, 3), dtype=np.uint8), mode="RGB")

    result = predict_fn(dummy_image, model_dict)

    norm = float(np.linalg.norm(result))
    assert abs(norm - 1.0) < 1e-5, f"Expected unit norm, got {norm}"


# ---------------------------------------------------------------------------
# output_fn
# ---------------------------------------------------------------------------

def test_output_fn_returns_json_with_embedding_key():
    sys.modules.pop('inference', None)
    from inference import output_fn

    embedding = np.random.rand(512).astype(np.float32)
    result = output_fn(embedding, "application/json")

    parsed = json.loads(result)
    assert "embedding" in parsed
    assert len(parsed["embedding"]) == 512


def test_output_fn_values_are_floats():
    sys.modules.pop('inference', None)
    from inference import output_fn

    embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    result = output_fn(embedding, "application/json")
    parsed = json.loads(result)

    for v in parsed["embedding"]:
        assert isinstance(v, float)
