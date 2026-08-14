#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "$script_dir/.." && pwd)"
install_dir="${LOCAL_IMAGE_INSTALL_DIR:-$project_dir/backend/data/local-image}"
runtime_dir="$install_dir/runtime"
model_dir="$install_dir/models"
upscaler_dir="$install_dir/upscaler-ncnn"
server_path="$(find "$runtime_dir" -type f -name sd-server -print -quit 2>/dev/null || true)"

if [[ -z "$server_path" ]]; then
  echo "sd-server belum terpasang. Jalankan scripts/install-local-image-model.sh" >&2
  exit 1
fi

required_models=(
  "$model_dir/z_image_turbo-Q3_K.gguf"
  "$model_dir/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
  "$model_dir/ae.safetensors"
  "$upscaler_dir/realesrgan-ncnn-vulkan"
  "$upscaler_dir/models/realesrgan-x4plus.bin"
  "$upscaler_dir/models/realesrgan-x4plus.param"
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

listen_port="${LOCAL_IMAGE_PORT:-7860}"
upstream_port="${LOCAL_IMAGE_UPSTREAM_PORT:-7861}"

"$server_path" \
  --listen-port "$upstream_port" \
  --diffusion-model "$model_dir/z_image_turbo-Q3_K.gguf" \
  --llm "$model_dir/Qwen3-4B-Instruct-2507-Q4_K_M.gguf" \
  --vae "$model_dir/ae.safetensors" \
  --cfg-scale 1.0 \
  --steps 8 \
  --diffusion-fa \
  --offload-to-cpu \
  --vae-tiling \
  --verbose &
server_pid=$!

cleanup() {
  kill "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

gateway_args=(
  --listen-port "$listen_port"
  --upstream-port "$upstream_port"
)
if [[ "${LOCAL_IMAGE_UPSCALER_ENABLED:-true}" == "true" ]]; then
  gateway_args+=(
    --upscaler-binary "$upscaler_dir/realesrgan-ncnn-vulkan"
    --upscaler-model-dir "$upscaler_dir/models"
    --upscaler-scale "${LOCAL_IMAGE_UPSCALER_SCALE:-4}"
    --upscaler-tile-size "${LOCAL_IMAGE_UPSCALER_TILE_SIZE:-128}"
    --upscaler-gpu-id "${LOCAL_IMAGE_UPSCALER_GPU_ID:-0}"
  )
fi

python3 "$script_dir/local-image-gateway.py" "${gateway_args[@]}"
