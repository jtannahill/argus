"""CLIP ViT-B/32 inference handler for SageMaker.

Generates 512-dimensional normalized image embeddings used by the
visual match Lambda to compare user photos against reference images.

Heavy dependencies (torch, clip) are imported lazily inside functions so that
the module can be imported and tested without the full GPU environment installed.
"""

import io
import json


def model_fn(model_dir):
    """Load CLIP ViT-B/32 from model_dir. Called once by SageMaker on startup.

    Returns a dict with keys: model, preprocess, device.
    """
    import clip  # openai/CLIP — only available in SageMaker / venv with requirements.txt
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device, download_root=model_dir)
    model.eval()
    return {"model": model, "preprocess": preprocess, "device": device}


def input_fn(request_body, content_type):
    """Decode incoming image bytes to a PIL Image.

    Accepts: image/jpeg, image/png, application/octet-stream.
    Returns: PIL.Image.Image in RGB mode.
    """
    from PIL import Image  # Pillow is always available; lazy for testability

    supported = {"image/jpeg", "image/png", "application/octet-stream"}
    if content_type not in supported:
        raise ValueError(
            f"Unsupported content type: {content_type}. "
            f"Supported types: {supported}"
        )
    image = Image.open(io.BytesIO(request_body)).convert("RGB")
    return image


def predict_fn(image, model_dict):
    """Generate a 512-dim normalized embedding for the given PIL Image.

    Args:
        image: PIL.Image.Image
        model_dict: dict returned by model_fn — {model, preprocess, device}

    Returns:
        numpy.ndarray of shape (512,), L2-normalized.
    """
    import numpy as np
    import torch

    model = model_dict["model"]
    preprocess = model_dict["preprocess"]
    device = model_dict["device"]

    image_input = preprocess(image).unsqueeze(0).to(device)

    with torch.no_grad():
        embedding = model.encode_image(image_input)

    # L2-normalize to unit vector so cosine similarity == dot product
    embedding = embedding / embedding.norm(dim=-1, keepdim=True)
    return embedding.squeeze(0).cpu().numpy()


def output_fn(embedding, content_type):
    """Serialize the embedding as JSON.

    Returns: JSON string {"embedding": [float, ...]} with 512 values.
    """
    return json.dumps({"embedding": embedding.tolist()})
