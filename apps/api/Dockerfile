FROM python:3.12-slim

WORKDIR /app

# System deps for Tesseract OCR (free, CPU-only — no GPU/CUDA needed)
# Replaces the old Marker/PyTorch stack, which required ~4.5GB of
# dependencies (CUDA libraries, transformers) the founder cannot
# run or afford pre-revenue. Tesseract + Poppler combined are <50MB.
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app into a proper Python package directory (api/), NOT
# directly into /app. This is required for main.py's relative
# imports (`from .core.config import settings`, `from .routers
# import ...`) to resolve correctly — Python only allows relative
# imports inside a recognized package. Copying main.py straight
# into /app and running `uvicorn main:app` makes it a top-level
# module with no parent package, which crashes immediately with
# "ImportError: attempted relative import with no known parent
# package" — this was caught and fixed by an actual boot test,
# not just a syntax check.
COPY . ./api/

# Non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Note the dotted module path: api.main:app, NOT main:app.
# Uvicorn adds the working directory (/app) to sys.path, so the
# `api` package (with its __init__.py) is importable, and every
# relative import inside it resolves correctly.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
