#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "$script_dir/.." && pwd)"
install_dir="${LOCAL_IMAGE_INSTALL_DIR:-$project_dir/backend/data/local-image}"
runtime_dir="$install_dir/runtime"
model_dir="$install_dir/models"
server_path="$(find "$runtime_dir" -type f -name sd-server -print -quit 2>/dev/null || true)"

if [[ -z "$server_path" ]]; then
  echo "sd-server belum terpasang. Jalankan scripts/install-local-image-model.sh" >&2
  exit 1
fi

required_models=(
  "$model_dir/z_image_turbo-Q3_K.gguf"
  "$model_dir/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
  "$model_dir/ae.safetensors"
)
for model_path in "${required_models[@]}"; do
  if [[ ! -s "$model_path" ]]; then
    echo "Model belum tersedia: $model_path" >&2
    exit 1
  fi
done

runtime_lib_dir="$(dirname "$server_path")"
export LD_LIBRARY_PATH="$runtime_lib_dir:${LD_LIBRARY_PATH:-}"
if [[ -f /usr/share/vulkan/icd.d/nvidia_icd.json ]]; then
  export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json
fi

exec "$server_path" \
  --listen-port "${LOCAL_IMAGE_PORT:-7860}" \
  --diffusion-model "$model_dir/z_image_turbo-Q3_K.gguf" \
  --llm "$model_dir/Qwen3-4B-Instruct-2507-Q4_K_M.gguf" \
  --vae "$model_dir/ae.safetensors" \
  --cfg-scale 1.0 \
  --steps 8 \
  --diffusion-fa \
  --offload-to-cpu \
  --clip-on-cpu \
  --vae-tiling \
  --verbose
