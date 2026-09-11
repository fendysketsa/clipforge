#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' \
    'Usage:' \
    '  render_short.sh --input FILE --output FILE --start SECONDS (--duration SECONDS | --end SECONDS)' \
    '                  [--subtitles FILE] [--fit blur|crop] [--replace-output]' \
    '' \
    'Renders a 1080x1920 H.264/AAC MP4 without modifying the source file.'
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 2
}

input=''
output=''
start=''
duration=''
end=''
subtitles=''
fit='blur'
replace_output=0

while (($#)); do
  case "$1" in
    --input) (($# >= 2)) || die '--input requires a value'; input=$2; shift 2 ;;
    --output) (($# >= 2)) || die '--output requires a value'; output=$2; shift 2 ;;
    --start) (($# >= 2)) || die '--start requires a value'; start=$2; shift 2 ;;
    --duration) (($# >= 2)) || die '--duration requires a value'; duration=$2; shift 2 ;;
    --end) (($# >= 2)) || die '--end requires a value'; end=$2; shift 2 ;;
    --subtitles) (($# >= 2)) || die '--subtitles requires a value'; subtitles=$2; shift 2 ;;
    --fit) (($# >= 2)) || die '--fit requires a value'; fit=$2; shift 2 ;;
    --replace-output) replace_output=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ -n $input ]] || die '--input is required'
[[ -n $output ]] || die '--output is required'
[[ -n $start ]] || die '--start is required'
[[ -f $input ]] || die "input does not exist: $input"
[[ $start =~ ^[0-9]+([.][0-9]+)?$ ]] || die '--start must be a non-negative number'
[[ $fit == blur || $fit == crop ]] || die '--fit must be blur or crop'
command -v ffmpeg >/dev/null 2>&1 || die 'ffmpeg is required'
command -v ffprobe >/dev/null 2>&1 || die 'ffprobe is required'
command -v realpath >/dev/null 2>&1 || die 'realpath is required'

if [[ -n $duration && -n $end ]]; then
  die 'use either --duration or --end, not both'
fi
if [[ -z $duration && -z $end ]]; then
  die 'one of --duration or --end is required'
fi
if [[ -n $duration ]]; then
  [[ $duration =~ ^[0-9]+([.][0-9]+)?$ ]] || die '--duration must be a positive number'
else
  [[ $end =~ ^[0-9]+([.][0-9]+)?$ ]] || die '--end must be a non-negative number'
  duration=$(awk -v clip_end="$end" -v clip_start="$start" 'BEGIN { printf "%.6f", clip_end - clip_start }')
fi
awk -v value="$duration" 'BEGIN { exit !(value > 0) }' || die 'duration must be greater than zero'

input_abs=$(realpath "$input")
output_dir=$(dirname "$output")
mkdir -p "$output_dir"
output_abs=$(realpath -m "$output")
[[ $input_abs != "$output_abs" ]] || die 'output must not be the source file'
if [[ -e $output_abs && $replace_output -ne 1 ]]; then
  die "output already exists; pass --replace-output to replace it: $output_abs"
fi

source_size=$(stat -c '%s' "$input_abs")
source_mtime=$(stat -c '%Y' "$input_abs")
output_base=$(basename "$output_abs")
temp_output=$(mktemp --tmpdir="$output_dir" ".${output_base}.XXXXXX.mp4")
cleanup() {
  if [[ -n ${temp_output:-} && -e $temp_output ]]; then
    rm -f -- "$temp_output"
  fi
}
trap cleanup EXIT INT TERM

subtitle_filter=''
if [[ -n $subtitles ]]; then
  [[ -f $subtitles ]] || die "subtitle file does not exist: $subtitles"
  subtitle_abs=$(realpath "$subtitles")
  subtitle_escaped=${subtitle_abs//\\/\\\\}
  subtitle_escaped=${subtitle_escaped//:/\\:}
  subtitle_escaped=${subtitle_escaped//\'/\\\'}
  subtitle_filter=",subtitles=filename='${subtitle_escaped}'"
fi

if [[ $fit == crop ]]; then
  video_filter="[0:v:0]scale=1080:1920:force_original_aspect_ratio=increase:force_divisible_by=2:flags=lanczos,crop=1080:1920,setsar=1${subtitle_filter}[vout]"
else
  video_filter="[0:v:0]split=2[bgsrc][fgsrc];[bgsrc]scale=1080:1920:force_original_aspect_ratio=increase:force_divisible_by=2:flags=bilinear,crop=1080:1920,gblur=sigma=28,eq=brightness=-0.16:saturation=1.08[bg];[fgsrc]scale=1080:1920:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1${subtitle_filter}[vout]"
fi

has_audio=$(ffprobe -v error -select_streams a:0 -show_entries stream=index -of csv=p=0 "$input_abs" | head -n 1)
common_args=(
  -hide_banner -loglevel warning -y
  -ss "$start" -t "$duration" -i "$input_abs"
)
video_args=(
  -map '[vout]'
  -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p
  -r 30 -movflags +faststart
)

if [[ -n $has_audio ]]; then
  filter_complex="${video_filter};[0:a:0]loudnorm=I=-16:LRA=7:TP=-1.5,aresample=async=1:first_pts=0[aout]"
  ffmpeg "${common_args[@]}" -filter_complex "$filter_complex" \
    "${video_args[@]}" -map '[aout]' -c:a aac -b:a 192k -shortest "$temp_output"
else
  ffmpeg "${common_args[@]}" -filter_complex "$video_filter" \
    "${video_args[@]}" -an "$temp_output"
fi

[[ -s $temp_output ]] || die 'ffmpeg did not create a usable output'
render_size=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$temp_output")
[[ $render_size == '1080x1920' ]] || die "unexpected output size: $render_size"
[[ $(stat -c '%s' "$input_abs") == "$source_size" ]] || die 'source size changed during render'
[[ $(stat -c '%Y' "$input_abs") == "$source_mtime" ]] || die 'source modification time changed during render'

if [[ -e $output_abs && $replace_output -eq 1 ]]; then
  mv -f -- "$temp_output" "$output_abs"
else
  mv -- "$temp_output" "$output_abs"
fi
temp_output=''
printf 'Rendered: %s\n' "$output_abs"

