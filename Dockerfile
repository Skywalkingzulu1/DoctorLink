FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH /app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create package structure
# We want: /app/projects/DoctorLink/
# And /app/projects/__init__.py
# And /app/projects/DoctorLink/__init__.py
RUN mkdir -p projects/DoctorLink

# Copy application files
COPY . projects/DoctorLink/

# Ensure __init__.py files exist
RUN touch projects/__init__.py
RUN touch projects/DoctorLink/__init__.py

# Expose the port
EXPOSE 8000

# Run the application
# We run from /app so projects.DoctorLink.main is discoverable
CMD ["gunicorn", "projects.DoctorLink.main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
