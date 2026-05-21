FROM python:3.13-slim

WORKDIR /app

# Install system deps for numpy and curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends gcc curl && \
    rm -rf /var/lib/apt/lists/*

# Copy source and install
COPY pyproject.toml .
COPY src/ src/
COPY run.py .
RUN pip install --no-cache-dir gunicorn . && \
    rm -rf /root/.cache

EXPOSE 5002

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5002", "--timeout", "300", "compliance_assistant_api.app:app"]
