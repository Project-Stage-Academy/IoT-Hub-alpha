FROM python:3.12-slim

WORKDIR /app

# install only what simulator needs
COPY ../requirements-dev.txt /app/backend/requirements-dev.txt
RUN pip install --no-cache-dir -r /app/backend/requirements-dev.txt

COPY simulator /app/simulator

ENTRYPOINT ["python", "-m", "simulator.run"]