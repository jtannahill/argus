"""Plate read inference — YOLOv8 detection + CRNN recognition.
Used by SageMaker Serverless Inference endpoint."""

import numpy as np
import cv2
import json


CHARSET = '_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'


def preprocess_image(img: np.ndarray, target_size: int = 640) -> np.ndarray:
    """Resize and pad image to target_size x target_size, normalize to [0,1]."""
    h, w = img.shape[:2]
    scale = target_size / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(img, (new_w, new_h))

    # Pad to square
    padded = np.zeros((target_size, target_size, 3), dtype=np.float32)
    padded[:new_h, :new_w] = resized.astype(np.float32) / 255.0

    # NCHW format
    return np.transpose(padded, (2, 0, 1))[np.newaxis, ...]


def decode_ctc_output(output: np.ndarray, charset: str = CHARSET) -> str:
    """Decode CTC output to string using best-path decoding."""
    indices = output[0] if output.ndim > 1 else output
    result = []
    prev = 0  # blank
    for idx in indices:
        idx = int(idx)
        if idx != prev and idx != 0:
            if idx < len(charset):
                result.append(charset[idx])
        prev = idx
    return ''.join(result)


def model_fn(model_dir):
    """Load YOLOv8 + CRNN models from model_dir. Called by SageMaker."""
    # Placeholder — will load actual ONNX models in training phase
    return {'detector': None, 'recognizer': None}


def input_fn(request_body, content_type):
    """Deserialize input image."""
    if content_type == 'application/x-image':
        img_array = np.frombuffer(request_body, dtype=np.uint8)
        return cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    elif content_type == 'application/json':
        data = json.loads(request_body)
        import boto3
        s3 = boto3.client('s3')
        obj = s3.get_object(Bucket=data['bucket'], Key=data['key'])
        img_array = np.frombuffer(obj['Body'].read(), dtype=np.uint8)
        return cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    raise ValueError(f'Unsupported content type: {content_type}')


def predict_fn(input_data, model):
    """Run detection + recognition. Returns plate text + confidence."""
    # Stub — returns placeholder until models are trained
    return {'refinedPlate': None, 'confidence': 0.0}


def output_fn(prediction, accept):
    """Serialize output."""
    return json.dumps(prediction), 'application/json'
