FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl tesseract-ocr tesseract-ocr-kor && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY k_jobscore ./k_jobscore
RUN pip install --no-cache-dir ".[ocr]"
ENV KJOBSCORE_HOME=/data
VOLUME /data
EXPOSE 8765
CMD ["sh", "-c", "[ -f /data/config.json ] || k-jobscore init; k-jobscore serve --host 0.0.0.0 --port 8765"]
