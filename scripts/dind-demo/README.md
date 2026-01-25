# Docker-in-Docker (DIND) demo

This is a demo-only Docker-in-Docker setup. It runs a nested Docker daemon and
starts a small compose stack inside the container.

Security warnings:
- DIND requires `--privileged`, which gives the container near-host level access.
- Do not use this in production or on untrusted machines.
- Use only for local demos or lab environments.

Build and run:

```bash
docker build -t iot-hub-dind-demo scripts/dind-demo
docker run --privileged --name iot-hub-dind-demo -d iot-hub-dind-demo
```

Stop and cleanup:

```bash
docker rm -f iot-hub-dind-demo
```

The inner demo stack is defined in `demo-compose.yml` and runs nginx + redis.
