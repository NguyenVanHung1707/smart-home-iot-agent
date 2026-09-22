#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "Usage: $0 PHOWHISPER_DIR OPENAI_WHISPER_DIR WHISPER_CPP_DIR OUTPUT_DIR" >&2
  exit 2
fi

phowhisper_dir=$1
openai_whisper_dir=$2
whisper_cpp_dir=$3
output_dir=$4

test -f "${phowhisper_dir}/config.json"
test -f "${whisper_cpp_dir}/models/convert-h5-to-ggml.py"
test -x "${whisper_cpp_dir}/build/bin/quantize"
mkdir -p "${output_dir}"

python3 "${whisper_cpp_dir}/models/convert-h5-to-ggml.py" \
  "${phowhisper_dir}" "${openai_whisper_dir}" "${output_dir}"
"${whisper_cpp_dir}/build/bin/quantize" \
  "${output_dir}/ggml-model.bin" "${output_dir}/ggml-phowhisper-tiny-q5_1.bin" q5_1

echo "Experimental model: ${output_dir}/ggml-phowhisper-tiny-q5_1.bin"
echo "Do not enable it until load, Vietnamese accuracy, latency, and RSS checks pass."
