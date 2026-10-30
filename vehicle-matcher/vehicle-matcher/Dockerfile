FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VM_DATABASE_URL=sqlite:////data/vehicles.db

WORKDIR /app

# Install dependencies first so this layer is cached between code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY tests ./tests

# Run as a non-root user; /data holds the SQLite file (mount a volume here to persist it).
RUN useradd --create-home appuser && mkdir /data && chown appuser /data
USER appuser

EXPOSE 8000

# On startup the app creates the tables and seeds the sample vehicles if the table is empty.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
