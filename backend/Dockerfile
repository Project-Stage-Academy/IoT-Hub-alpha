FROM python:3.13

RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Development only - in production this should be replaced with gunicorn.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
