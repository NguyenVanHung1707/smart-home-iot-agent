#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
zipformer_name="sherpa-onnx-zipformer-vi-int8-2025-04-20"
zipformer_dir="${repo_root}/models/zipformer/${zipformer_name}"
mkdir -p "${repo_root}/models/piper" "${repo_root}/models/zipformer"

download() {
  local url=$1
  local destination=$2
  if [[ -f "${destination}" ]]; then
    echo "Already present: ${destination#"${repo_root}/"}"
    return
  fi
  curl --fail --location --retry 3 --output "${destination}.part" "${url}"
  mv "${destination}.part" "${destination}"
}

verify_sha256() {
  local expected=$1
  local file=$2
  echo "${expected}  ${file}" | sha256sum --check --status
}

download_zipformer() {
  local temp_dir archive extracted
  temp_dir=$(mktemp -d)
  archive="${temp_dir}/${zipformer_name}.tar.bz2"
  extracted="${temp_dir}/${zipformer_name}"
  trap 'rm -rf "${temp_dir}"' RETURN

  curl --fail --location --retry 3 --output "${archive}" \
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/${zipformer_name}.tar.bz2"
  verify_sha256 "48d0fdc9b3515eb9b00c4dfec2883207ee5ebe5c95b1959e7afce87fc3391938" "${archive}"
  tar -xjf "${archive}" -C "${temp_dir}"

  for file in encoder-epoch-12-avg-8.int8.onnx decoder-epoch-12-avg-8.onnx joiner-epoch-12-avg-8.int8.onnx tokens.txt; do
    install -Dm 0644 "${extracted}/${file}" "${zipformer_dir}/${file}"
  done
}

if ! (cd "${repo_root}" && grep 'models/zipformer/' scripts/voice-models.sha256 | sha256sum --check --status); then
  download_zipformer
fi
download "https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx" \
  "${repo_root}/models/piper/vi_VN-vais1000-medium.onnx"
download "https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx.json" \
  "${repo_root}/models/piper/vi_VN-vais1000-medium.onnx.json"

cd "${repo_root}"
sha256sum --check scripts/voice-models.sha256
echo "Voice models downloaded and verified."
