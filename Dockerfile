FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    poppler-utils \
    libgl1-mesa-glx \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first for better caching
COPY pyproject.toml ./
RUN pip install --no-cache-dir .[db]

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy the rest of the application code
COPY thoa_screening ./thoa_screening

# Set PYTHONPATH so absolute imports work
ENV PYTHONPATH=/app

# Command is overridden in docker-compose.yml
CMD ["uvicorn", "thoa_screening.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
