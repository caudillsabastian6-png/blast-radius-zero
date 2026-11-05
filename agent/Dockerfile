# Blast Radius Zero - agent (control plane) image.
# Needs the docker CLI to launch per-run sandbox containers on the host's
# Docker daemon (socket is mounted by docker-compose; see ARCHITECTURE.md
# for the trust-boundary discussion). Python code is standard library only.
#
# Build context is the REPO ROOT (see docker-compose.yml) so this file can
# bake in both the agent code and the demo sample tasks.
FROM docker:27-cli AS dockercli
FROM python:3.12-slim

COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker

WORKDIR /srv
COPY agent/app /srv/app
COPY agent/requirements.txt /srv/requirements.txt
# Demo sample tasks, baked in: app/main.py resolves PROJECT_ROOT as
# parents[2] of app/main.py — "/" in this image — so the samples it reads
# (demo/sample_tasks/tasks.json + seed files) must live at /demo.
COPY demo /demo

ENV PYTHONDONTWRITEBYTECODE=1 BRZ_RUNS_DIR=/srv/runs
EXPOSE 8080
CMD ["python3", "-m", "app.main"]
