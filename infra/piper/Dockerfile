FROM python:3.11-slim

RUN python -m pip install --no-cache-dir "piper-tts[http]==1.6.0" \
    && useradd --create-home --uid 10001 piper

USER piper
EXPOSE 5000
ENTRYPOINT ["python", "-m", "piper.http_server"]
