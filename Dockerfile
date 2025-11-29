FROM python:3.11-slim

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Verzeichnisse erstellen und Rechte setzen
RUN mkdir -p /app/data /app/uploads && \
    chmod 777 /app/data /app/uploads

# Non-root user mit korrekten Rechten
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:create_app()"]
