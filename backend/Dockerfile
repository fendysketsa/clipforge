FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    IMAGEIO_FFMPEG_EXE=/usr/bin/ffmpeg \
    FFMPEG_BINARY=/usr/bin/ffmpeg

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      ffmpeg \
      libglib2.0-0 \
      libgl1 \
      libgomp1 \
      fontconfig \
      fonts-dejavu-core \
      fonts-dejavu \
      fonts-liberation \
      fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

RUN python -m playwright install --with-deps chromium

RUN python -c "import cv2, sys; missing = [name for name in ('VideoCapture', 'CascadeClassifier', 'HOGDescriptor') if not hasattr(cv2, name)]; print(f'OpenCV install is incomplete, missing: {missing}' if missing else f'OpenCV {cv2.__version__} ready'); sys.exit(1 if missing else 0)"

COPY . .

RUN mkdir -p outputs uploads data

EXPOSE 8010

CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8010"]
