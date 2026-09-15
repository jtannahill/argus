#!/bin/bash
# Package CLIP ViT-B/32 for SageMaker Serverless
# Run this in a Docker container or environment with PyTorch + CLIP installed
#
# Usage: ./package_model.sh
# Output: model.tar.gz ready to upload to S3

set -e

echo "Installing dependencies..."
pip install torch clip-by-openai Pillow numpy --quiet

echo "Downloading CLIP ViT-B/32..."
python3 -c "
import clip
import torch
import os

model, preprocess = clip.load('ViT-B/32', device='cpu', download_root='./model_data')
print(f'Model downloaded to ./model_data')
print(f'Files: {os.listdir(\"./model_data\")}')
"

echo "Copying inference handler..."
cp inference.py model_data/code/inference.py 2>/dev/null || {
    mkdir -p model_data/code
    cp inference.py model_data/code/inference.py
}

echo "Creating model.tar.gz..."
cd model_data
tar -czf ../model.tar.gz .
cd ..

echo "Uploading to S3..."
BUCKET=$(aws cloudformation describe-stacks --stack-name ArgusData \
    --query 'Stacks[0].Outputs[?OutputKey==`ArgusTrainingBucket`].OutputValue' \
    --output text 2>/dev/null || echo "argusdata-trainingbucketeb7bb5c9-vdmqup1qfnor")

aws s3 cp model.tar.gz "s3://${BUCKET}/models/clip-embedding/model.tar.gz"

echo "Done! Model uploaded to s3://${BUCKET}/models/clip-embedding/model.tar.gz"
echo "Redeploy ArgusMl stack to pick up the new model."
