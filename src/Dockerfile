FROM python:3.13.3-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpango1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libcairo2 \
    libpango1.0-dev \
    libgdk-pixbuf2.0-dev \
    libxml2-dev \
    libxslt1-dev \
    libjpeg-dev \
    zlib1g-dev \
    libglib2.0-0 \
    && apt-get clean

# Create a non-root user
RUN useradd -ms /bin/bash celeryuser

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy entire project
COPY . .

# Give permissions to the new user
RUN chown -R celeryuser:celeryuser /app

# Switch to non-root user
USER celeryuser

EXPOSE 8000

# Default command for app service (Celery overrides this)
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
