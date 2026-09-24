#!/bin/bash
set -e

echo "Installing system dependencies for OCR pipeline..."

if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macOS detected. Using Homebrew..."
    brew install tesseract poppler
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Linux detected. Using apt-get..."
    sudo apt-get update
    sudo apt-get install -y tesseract-ocr poppler-utils
else
    echo "Unsupported OS. Please install tesseract and poppler manually."
    exit 1
fi

echo "Installing Python dependencies..."
# Use pip to install the updated pyproject.toml dependencies
python -m pip install -e .

echo "Downloading SpaCy NER model..."
python -m spacy download en_core_web_sm

echo "OCR dependencies installed successfully!"
