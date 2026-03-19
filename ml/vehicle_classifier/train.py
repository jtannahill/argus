"""Training script for vehicle classifier.
Fine-tunes EfficientNet-B3 with multi-head output (make, model, year, color).
Runs as SageMaker Training Job."""

import argparse
import os


def train(data_dir, output_dir, epochs=30, batch_size=32):
    """Fine-tune EfficientNet-B3 on Stanford Cars + CompCars."""
    print(f'[STUB] Vehicle classifier training: {epochs} epochs, batch {batch_size}')
    os.makedirs(output_dir, exist_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default=os.environ.get('SM_CHANNEL_TRAINING', '/opt/ml/input/data'))
    parser.add_argument('--output-dir', default=os.environ.get('SM_MODEL_DIR', '/opt/ml/model'))
    parser.add_argument('--epochs', type=int, default=30)
    parser.add_argument('--batch-size', type=int, default=32)
    args = parser.parse_args()

    train(args.data_dir, args.output_dir, args.epochs, args.batch_size)
