# Blast Radius Zero - sandbox worker image.
# Deliberately minimal: Python + bash + coreutils. No network clients beyond
# what bash/coreutils ship (the container runs with --network none anyway),
# no secrets, no data. The agent launches this image once per run with the
# hardening flags in agent/app/sandbox_client.py and destroys it afterwards.
FROM python:3.12-slim

WORKDIR /app
# --chmod matters: source trees with group-only modes (e.g. 660) would
# otherwise leave executor.py unreadable by the nobody user below.
COPY --chmod=644 executor.py /app/executor.py

# The executor runs as an unprivileged user; the agent additionally pins
# --user 65534:65534 at launch time.
USER 65534:65534
ENV BRZ_WORKSPACE=/workspace PYTHONDONTWRITEBYTECODE=1
# The python base image bakes in GPG_KEY (its public release-signing
# fingerprint - public material, but key-named). Scrub it so the sandbox
# environment carries nothing that even looks like a key.
ENTRYPOINT ["env", "-u", "GPG_KEY", "python3", "/app/executor.py"]
