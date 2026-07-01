FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=7860 \
    WHISPER_MODEL_SIZE=base \
    WHISPER_DEVICE=cpu \
    WHISPER_COMPUTE_TYPE=int8 \
    STREAM_LANGUAGE=bg \
    REALTIME_INTERVAL=2.2 \
    ROLLING_WINDOW_MB=12 \
    STREAM_MAX_BUFFER_MB=60 \
    MAX_MEDIA_MB=80 \
    DB_ENABLED=1 \
    DB_SSLMODE=require

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 7860

CMD ["python", "persistent_launch.py"]
