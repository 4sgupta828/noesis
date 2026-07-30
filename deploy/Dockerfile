# Noesis API image — the vertical-neutral product surface.
FROM python:3.13-slim

WORKDIR /app
RUN pip install --no-cache-dir --upgrade pip

# Install the kernel (with serve + postgres extras) and the active vertical.
COPY packages packages
COPY apps apps
COPY deploy deploy
RUN pip install --no-cache-dir "./packages/kernel[serve,postgres]" ./packages/vertical_regulatory

# apps/ is not a pip package; put it on the path. Single vertical per deployment.
ENV PYTHONPATH=/app/apps \
    NOESIS_ACTIVE_VERTICAL=regulatory \
    NOESIS_PROVIDER_MODE=replay \
    PORT=8000

EXPOSE 8000
CMD ["bash", "deploy/start.sh"]
