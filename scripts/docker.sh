#!/usr/bin/env bash
# Start the local Compose stack with the optional runtimes requested by the user.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/docker.sh up [base|voice|llm|full]
  bash scripts/docker.sh down [base|voice|llm|full]
  bash scripts/docker.sh ps
  bash scripts/docker.sh logs [service ...]
  bash scripts/docker.sh config

Modes:
  base         backend, dashboard, MQTT, and device simulator (default)
  voice        base plus Vietnamese STT/TTS
  llm          base plus llama.cpp local model
  full         base plus Vietnamese STT/TTS and llama.cpp
  tunnel       base plus Cloudflare Tunnel
  full-tunnel  all components plus Cloudflare Tunnel
EOF
}

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is required. Install Docker Desktop or the Docker Compose plugin." >&2
  exit 1
fi

command="${1:-up}"

case "$command" in
  up|down)
    mode="${2:-base}"
    profiles=()
    case "$mode" in
      base) ;;
      voice) profiles+=(--profile voice) ;;
      llm) profiles+=(--profile local-llm) ;;
      full) profiles+=(--profile local-llm --profile voice) ;;
      tunnel) profiles+=(--profile tunnel) ;;
      full-tunnel) profiles+=(--profile local-llm --profile voice --profile tunnel) ;;
      *)
        echo "Unknown mode: $mode" >&2
        usage >&2
        exit 2
        ;;
    esac

    # Auto-enable tunnel profile if CLOUDFLARE_TUNNEL_TOKEN is configured and not already included
    if [[ -f .env ]] && grep -q '^CLOUDFLARE_TUNNEL_TOKEN=.\+' .env 2>/dev/null; then
      if [[ ! " ${profiles[*]} " =~ " --profile tunnel " ]]; then
        profiles+=(--profile tunnel)
      fi
    fi
    [[ $# -le 2 ]] || { usage >&2; exit 2; }
    if [[ "$command" == "down" ]]; then
      docker compose "${profiles[@]}" down
      exit 0
    fi
    if [[ "$mode" == "voice" || "$mode" == "full" || "$mode" == "full-tunnel" ]]; then
      echo "Checking Vietnamese Zipformer and Piper models..."
      bash scripts/download_voice_models.sh
    fi
    docker compose "${profiles[@]}" up --build -d
    echo
    echo "Dashboard:  http://localhost/"
    echo "Domain:     https://lophocso.io.vn (Cloudflare Tunnel)"
    echo "API docs:   http://localhost:8000/docs"
    echo "API health: http://localhost:8000/health"
    if [[ "$mode" == "llm" || "$mode" == "full" || "$mode" == "full-tunnel" ]]; then
      echo "LLM health: http://localhost:8080/health"
    fi
    echo "MQTT LAN:   0.0.0.0:1883 (TCP cho ESP32 trong mạng WiFi LAN)"
    echo "MQTT WS:    ws://localhost:9001"
    ;;
  ps)
    [[ $# -eq 1 ]] || { usage >&2; exit 2; }
    docker compose ps
    ;;
  logs)
    shift
    docker compose logs -f "$@"
    ;;
  config)
    [[ $# -eq 1 ]] || { usage >&2; exit 2; }
    docker compose config
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown command: $command" >&2
    usage >&2
    exit 2
    ;;
esac
