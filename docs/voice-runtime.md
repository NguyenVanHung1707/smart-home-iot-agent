# Local voice runtime

## Setup

Download the pinned models before the offline test:

```bash
bash scripts/download_voice_models.sh
```

Enable the speech services in `.env` and start the stack:

```text
VOICE_ENABLED=true
ZIPFORMER_MODEL_DIR=models/zipformer/sherpa-onnx-zipformer-vi-int8-2025-04-20
ZIPFORMER_NUM_THREADS=2
PIPER_VOICE=vi_VN-vais1000-medium
```

Zipformer dùng CPU provider và greedy search. Trên Raspberry Pi 4, bắt đầu với
hai threads rồi benchmark 1, 2 và 4 threads trên cùng manifest.

```bash
docker compose --profile voice up --build
```

Piper is reachable only inside the Compose network; Zipformer runs in the
FastAPI process. Browser VAD sends mono PCM WAV at 16 kHz after two seconds of
silence, with a 20-second fallback. FastAPI validates and decodes the upload to
float32 once; audio stays in request memory and is not saved.

## APIs

- `POST /api/v1/voice/transcribe`: multipart field `file`, WAV PCM 16-bit mono 16 kHz, maximum 20 seconds.
- `POST /api/v1/voice/process`: confirmed transcript; this remains the shared text/voice agent path.
- `POST /api/v1/voice/synthesize`: JSON `{ "text": "..." }`, returns `audio/wav`.
- `GET /api/v1/voice/status`: configured model, voice, and runtime readiness.

For a USB microphone and speaker attached to the Pi:

```bash
python -m src.voice_cli --duration 10
```

This requires ALSA `arecord` and `aplay`. It creates files only in a temporary
directory and removes them on success or failure.

## Benchmark and model selection

Benchmark `ZIPFORMER_NUM_THREADS=1,2,4` against the same local Vietnamese
command manifest. Record real-time factor, median/p95 latency, voice-to-action
latency, and peak RSS; select the lowest median RTF that also meets the resource
gates: median RTF below 1, voice-to-action median/p95 at most 12/18 seconds,
full-stack RAM at most 3.6 GB, and no OOM or throttling. Raw user recordings
stay outside Git. Without a private Vietnamese command manifest, publish only
smoke and latency results, not CER/WER claims.

The downloader does not use PyTorch/K2 checkpoints or the 1.4 GB Zipformer
variant. Existing local copies remain untouched and are outside the runtime path.

The manifest is JSONL with paths relative to the manifest file:

```json
{"audio": "audio/command-001.wav", "reference": "bật đèn phòng khách"}
```

Run the aggregate STT benchmark once per configured model. The report contains
only aggregate metrics, not transcripts or reference text:

```bash
python scripts/benchmark_voice.py eval/local-voice/manifest.jsonl \
  --model-label sherpa-onnx-zipformer-vi-int8-2025-04-20 \
  --output eval/results/voice-zipformer.json
```
