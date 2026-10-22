FROM node:22-bookworm-slim AS node-runtime

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LD_LIBRARY_PATH=/usr/local/lib/python3.12/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.12/site-packages/nvidia/cudnn/lib \
    IMAGEIO_FFMPEG_EXE=/usr/bin/ffmpeg \
    FFMPEG_BINARY=/usr/bin/ffmpeg \
    PYTHON_SUBPROCESS_FILE=/usr/local/lib/python3.12/subprocess.py \
    PYTHON_SUBPROCESS_BACKUP=/opt/python-stdlib-backup/subprocess.py

WORKDIR /app

ARG DENO_VERSION=2.5.5

COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version \
    && npm --version

# The local Docker/BuildKit snapshot has previously contained a raw 0xA0 byte
# in subprocess.py. Repair that byte before pip (which imports subprocess), then
# keep the verified file as the runtime recovery source.
RUN stdlib_repaired="${PYTHON_SUBPROCESS_FILE}.repaired" \
    && LC_ALL=C tr '\240' ' ' < "$PYTHON_SUBPROCESS_FILE" > "$stdlib_repaired" \
    && mv "$stdlib_repaired" "$PYTHON_SUBPROCESS_FILE" \
    && python -m py_compile "$PYTHON_SUBPROCESS_FILE" \
    && python -c "import subprocess; print(f'Python subprocess runtime repaired: {subprocess.__file__}')" \
    && mkdir -p /opt/python-stdlib-backup \
    && cp "$PYTHON_SUBPROCESS_FILE" "$PYTHON_SUBPROCESS_BACKUP" \
    && chmod 0444 "$PYTHON_SUBPROCESS_BACKUP" \
    && python -m py_compile "$PYTHON_SUBPROCESS_BACKUP"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      ffmpeg \
      libglib2.0-0 \
      libgl1 \
      libgomp1 \
      fontconfig \
      fonts-dejavu-core \
      fonts-dejavu \
      fonts-liberation \
      fonts-noto-core \
      espeak-ng \
      procps \
      unzip \
    && curl -fsSLo /tmp/deno.zip \
      "https://github.com/denoland/deno/releases/download/v${DENO_VERSION}/deno-x86_64-unknown-linux-gnu.zip" \
    && unzip -q /tmp/deno.zip -d /usr/local/bin \
    && chmod 0755 /usr/local/bin/deno \
    && deno --version \
    && rm -f /tmp/deno.zip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

RUN python -m playwright install --with-deps chromium

RUN python -c "import cv2, sys; missing = [name for name in ('VideoCapture', 'CascadeClassifier', 'HOGDescriptor') if not hasattr(cv2, name)]; print(f'OpenCV install is incomplete, missing: {missing}' if missing else f'OpenCV {cv2.__version__} ready'); sys.exit(1 if missing else 0)"

COPY . .

# Hypit authors the semantic narration surface; Remotion owns visual assembly.
# Install from the audited lockfile without package lifecycle scripts. The
# renderer reuses Chromium installed by Playwright above.
RUN cd /app/remotion \
    && npm ci --omit=dev --ignore-scripts \
    && npm cache clean --force

RUN chmod 0755 /app/docker-entrypoint.sh \
    && mkdir -p outputs uploads data

EXPOSE 8010

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8010"]
