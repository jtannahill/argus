"""Vehicle classifier inference — EfficientNet-B3 multi-head.
Predicts make, model, year, color from vehicle images."""

import numpy as np
import cv2
import json


def preprocess_image(img: np.ndarray, target_size: int = 300) -> np.ndarray:
    """Resize to target_size x target_size, normalize with ImageNet stats."""
    resized = cv2.resize(img, (target_size, target_size))
    normalized = resized.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406])
    std = np.array([0.229, 0.224, 0.225])
    normalized = (normalized - mean) / std
    return np.transpose(normalized, (2, 0, 1))[np.newaxis, ...]


def decode_predictions(outputs: dict, labels: dict) -> dict:
    """Decode multi-head softmax outputs to label strings."""
    result = {}
    for head in ['make', 'model', 'year', 'color']:
        if head in outputs and head in labels:
            probs = outputs[head][0]
            idx = int(np.argmax(probs))
            result[head] = labels[head][idx] if idx < len(labels[head]) else None
            result[f'{head}_confidence'] = float(probs[idx])
        else:
            result[head] = None
    return result


def model_fn(model_dir):
    """Load EfficientNet model + label mappings."""
    return {'model': None, 'labels': {}}


def input_fn(request_body, content_type):
    """Deserialize input."""
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
    """Run classification. Stub until model is trained."""
    return {'make': None, 'model': None, 'year': None, 'color': None}


def output_fn(prediction, accept):
    return json.dumps(prediction), 'application/json'
