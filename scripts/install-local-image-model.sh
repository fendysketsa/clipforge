#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "$script_dir/.." && pwd)"
install_dir="${LOCAL_IMAGE_INSTALL_DIR:-$project_dir/backend/data/local-image}"
runtime_dir="$install_dir/runtime"
model_dir="$install_dir/models"
download_dir="$install_dir/downloads"
upscaler_dir="$install_dir/upscaler-ncnn"

runtime_name="sd-master-de298c2-bin-Linux-Ubuntu-24.04-x86_64-vulkan.zip"
runtime_url="https://github.com/leejet/stable-diffusion.cpp/releases/download/master-820-de298c2/$runtime_name"
runtime_sha="945b697995d8c7dbde6323d04177d7c12d29091ca84796b423f9ab6c660090ad"

diffusion_name="z_image_turbo-Q3_K.gguf"
diffusion_url="https://huggingface.co/leejet/Z-Image-Turbo-GGUF/resolve/main/$diffusion_name"
diffusion_sha="4b44bdaa7814f20d7cf144e3939bd93aa32f50660204dd0c2aea5c5376232980"

text_encoder_name="Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
text_encoder_url="https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/$text_encoder_name"
text_encoder_sha="3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"

vae_name="ae.safetensors"
vae_url="https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/$vae_name"
vae_sha="afc8e28272cd15db3919bacdb6918ce9c1ed22e96cb12c4d5ed0fba823529e38"

upscaler_archive_name="realesrgan-ncnn-vulkan-20220424-ubuntu.zip"
upscaler_url="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/$upscaler_archive_name"
upscaler_sha="e5aa6eb131234b87c0c51f82b89390f5e3e642b7b70f2b9bbe95b6a285a40c96"

for command_name in curl sha256sum unzip; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Perintah wajib belum tersedia: $command_name" >&2
    exit 1
  fi
done

available_kb="$(df -Pk "$project_dir" | awk 'NR==2 {print $4}')"
if [[ "${available_kb:-0}" -lt 10485760 ]]; then
  echo "Butuh sedikitnya 10 GB ruang kosong untuk runtime, model, dan file sementara." >&2
  exit 1
fi

mkdir -p "$runtime_dir" "$model_dir" "$download_dir" "$upscaler_dir"

verified_download() {
  local url="$1"
  local target="$2"
  local expected_sha="$3"
  local label="$4"

  if [[ -f "$target" ]] && printf '%s  %s\n' "$expected_sha" "$target" | sha256sum --check --status; then
    echo "$label sudah ada dan checksum valid."
    return
  fi
  if [[ -f "$target" ]]; then
    mv "$target" "$target.invalid.$(date +%Y%m%d%H%M%S)"
  fi
  echo "Mengunduh $label ..."
  curl --fail --location --retry 5 --retry-delay 3 --continue-at - --output "$target" "$url"
  printf '%s  %s\n' "$expected_sha" "$target" | sha256sum --check
}

runtime_archive="$download_dir/$runtime_name"
verified_download "$runtime_url" "$runtime_archive" "$runtime_sha" "stable-diffusion.cpp Vulkan"
verified_download "$diffusion_url" "$model_dir/$diffusion_name" "$diffusion_sha" "Z-Image-Turbo Q3"
verified_download "$text_encoder_url" "$model_dir/$text_encoder_name" "$text_encoder_sha" "Qwen3 text encoder Q4"
verified_download "$vae_url" "$model_dir/$vae_name" "$vae_sha" "Z-Image VAE"
upscaler_archive="$download_dir/$upscaler_archive_name"
verified_download "$upscaler_url" "$upscaler_archive" "$upscaler_sha" "Real-ESRGAN NCNN-Vulkan"

unzip -o -q "$runtime_archive" -d "$runtime_dir"
unzip -o -q "$upscaler_archive" -d "$upscaler_dir"
server_path="$(find "$runtime_dir" -type f -name sd-server -print -quit)"
if [[ -z "$server_path" ]]; then
  echo "Binary sd-server tidak ditemukan setelah ekstraksi." >&2
  exit 1
fi
chmod u+x "$server_path"
chmod u+x "$upscaler_dir/realesrgan-ncnn-vulkan"

cat <<EOF
Instalasi image model lokal selesai.
Runtime : $server_path
Model   : $model_dir/$diffusion_name
Upscaler: $upscaler_dir/realesrgan-ncnn-vulkan
Ukuran  : $(du -sh "$install_dir" | awk '{print $1}')
Jalankan: $project_dir/scripts/start-local-image-model.sh
EOF
