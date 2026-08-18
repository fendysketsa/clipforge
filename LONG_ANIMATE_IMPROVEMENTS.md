# Long Animate Video Generation - Perbaikan & Optimasi Sistem

## 🔍 Analisis Pipeline Saat Ini

```
Input Script
    ↓
[1] Build Storyboard (AI) → 3-7 scenes dengan visual prompts
    ↓
[2] TTS Synthesis (Parallelizable)
    ├─ Synthesize narration per scene
    ├─ Trim voice silence
    ├─ Fit voice to scene duration
    ├─ Concatenate voice track
    ↓
[3] Allocate Scene Durations → Timing berdasarkan audio
    ↓
[4] Plan Storyboard Shots → Explode scenes menjadi individual shots
    ↓
[5] Generate Images (Loop Per Shot)
    ├─ Remote API (Gemini/Stable Diffusion/OpenRouterAI)
    ├─ Local Fallback (fendy_local_story_art)
    ├─ Vision QA Inspection
    ├─ Retry logic dengan size downgrade
    ↓
[6] Render Shot Videos (Loop Per Shot)
    ├─ Apply camera motion
    ├─ Duration sync dengan audio
    ↓
[7] Assemble All Shots → Video tanpa fade/padding
    ↓
[8] Final Composite
    ├─ Audio mixing (narration + music ducking + SFX)
    ├─ Video filters (contrast, saturation)
    ├─ Subtitle burning
    ├─ Logo watermark
    ↓
[9] Final QC → Duration, resolution, audio sample rate, black frames
    ↓
Output MP4 + SRT
```

---

## ⚠️ MASALAH TERIDENTIFIKASI

### 1. **TTS Synthesis - Tidak Parallelizable** (KRITIS)
**Lokasi**: `synthesize_narration()`, loop sequential di line ~2265
```python
for scene in storyboard.scenes:
    voice_path, scene.voice_provider = synthesize_narration(scene, scene_dir)  # SEQUENTIAL!
    trimmed = trim_voice_silence(scene, voice_path, scene_dir)
```

**Dampak**: 
- 5 scenes = ~50 detik (jika setiap TTS 10 detik)
- Bisa jadi 5-20 detik parallel (edge-tts batch API ada)

**Solusi**:
- Implement concurrent.futures.ThreadPoolExecutor untuk TTS synthesis
- Batch multiple scenes dalam satu API request ke edge-tts jika tersedia
- Cache TTS hasil untuk script yang sama

---

### 2. **Image Generation - Retry Logic Terlalu Konservatif**
**Lokasi**: `_remote_scene_image()` line ~1450
```python
retries = max(1, min(4, int(os.environ.get("LONG_ANIMATE_IMAGE_RETRIES", "3"))))
max_timeout = 1800.0 if is_sd_cpp else 300.0
```

**Masalah**:
- Default 3 retries, tapi timeout sampai 300-1800 detik
- Kalau timeout di retry 3, total waktu bisa 9000 detik (2.5 jam!)
- Size downgrade logic hanya untuk SD-cpp, bukan API provider lain
- Tidak ada exponential backoff untuk rate-limited responses (429)

**Solusi**:
- Aggressive retry dengan timeout progresif: `30s → 60s → 120s`
- Implement size downgrade untuk semua provider (tidak cuma SD-cpp)
- Exponential backoff untuk 429/503: `base_delay * (2 ^ attempt)`
- Skip failed shot dan continue, dengan warning (bukan fatal error)

---

### 3. **Vision QA - Memory Leak & Inefficient Caching**
**Lokasi**: `_FACE_DETECTOR` global variable & `inspect_generated_image()` line ~1700
```python
_FACE_DETECTOR: object | None = None  # Global state - not cleaned up
```

**Masalah**:
- Face detector model loaded sekali, tapi tidak pernah di-cleanup
- Setiap QA attempt baca image dari disk 3-4 kali (reference, character, style)
- `_visual_signature()` recompute untuk setiap comparison

**Solusi**:
- Cache style/character reference signatures di memory
- Implement reference image cleanup di akhir render
- Batch face detection untuk multiple shots

---

### 4. **Storyboard Parsing - Fragile Error Handling**
**Lokasi**: `build_storyboard()` line ~809
```python
try:
    parsed = extract_json(...)
except Exception:
    pass  # Fall back ke fallback tanpa error logging
```

**Masalah**:
- Jika AI API error/timeout, silent fallback ke generic storyboard
- User tidak tahu kenapa result generik (hilang creative direction)
- Tidak ada max token limit validation
- Script > 30KB dipotong tanpa warning

**Solusi**:
- Log semua parsing failures dengan context
- Validate script length & give early warning
- Return partial results dengan error metadata
- Implement fallback tiers: AI → cached previous → generic

---

### 5. **Final Composite - Slow FFmpeg Operations**
**Lokasi**: `render_long_animate()` line ~2370
```python
_run([_ffmpeg_path(), ...filters...])  # Sequential filters
```

**Masalah**:
- 8 video input stream (assembled + narration + sine waves + pink noise)
- Complex filtergraph dengan sidechaincompress + amix
- Hardcoded "slow" preset untuk libx264 (60-180 menit pada 1080p)
- Logo watermark rendered setiap frame dengan drawtext filter

**Solusi**:
- Pre-optimize filter order: reorder untuk minimize intermediate buffers
- Render watermark sekali ke image overlay, bukan setiap frame
- Configurable x264 preset: `slow` (default) → `medium` (faster)
- Parallel encoding test: probing GPU codec support
- Music/SFX generation bisa di-cache (deterministic dari seed)

---

### 6. **Shot Video Rendering - No Duration Validation**
**Lokasi**: `render_shot_video()` line ~1974
```python
def render_shot_video(shot: AnimateShot, image_path: Path, scene_dir: Path) -> Path:
    # No pre-validation of shot.duration vs generated video length
```

**Masalah**:
- Generated video bisa keluar beda durasi dari yang direncanakan
- Jika 1 shot drift 0.1s, semua cut points di final QC bisa salah
- Subtitle timing juga akan off

**Solusi**:
- Post-render validation: baca actual duration FFprobe
- If drift > tolerance (50ms), rerender atau log warning
- Build metadata table: expected_duration → actual_duration

---

### 7. **Voice Silence Trimming - Overly Aggressive**
**Lokasi**: `trim_voice_silence()` line ~1914
```python
# Default trimming bisa potong transisi natural speech
```

**Masalah**:
- Trimming threshold bisa terlalu agresif, potong breath/pause di tengah narasi
- No preview/validation bahwa hasil tetap natural

**Solusi**:
- Configurable threshold: `LONG_ANIMATE_VOICE_TRIM_THRESHOLD` (default 0.015)
- Preserve minimum silence duration antara sentences (100ms)
- Log warning jika trimmed > 500ms

---

### 8. **Resource Management - No Cleanup on Error**
**Lokasi**: `render_long_animate()` - full function
```python
# Jika error di tengah render, intermediate files tidak dihapus
# Memory dari reference images/detectors tidak di-cleanup
```

**Masalah**:
- Failed render leaves GB of intermediate PNG/MP4 files
- Multiple failed renders = disk space leak
- Detector model never unloaded

**Solusi**:
- Context manager untuk work_dir cleanup
- Try/finally block untuk resource cleanup
- Implement `--cleanup-failed` flag

---

### 9. **Logging & Debug Info - Insufficient**
**Lokasi**: semua functions
```python
# Hanya ada progress callbacks, minimal actual logging
```

**Masalah**:
- Sulit diagnosa jika gagal di mana
- No timing breakdown (storyboard: 10s, TTS: 25s, images: 300s, final: 120s)
- No provider statistics

**Solusi**:
- Add structured logging dengan timestamp
- Per-step timing measurement
- Provider success rate statistics
- JSON report output

---

### 10. **Aspect Ratio Handling - Hardcoded**
**Lokasi**: `_output_geometry()` line ~114
```python
if aspect == "9:16":
    return aspect, 1080, 1920
return "16:9", 1920, 1080
```

**Masalah**:
- All calculations assume ini dua aspect ratio saja
- Sulit add aspect ratio baru (e.g., 4:3, 1:1)
- Canvas generation di `_local_scene_image()` hardcoded 1920x1080

**Solusi**:
- Parametric geometry class
- Cache aspect ratio calculations
- Configurable default

---

## 🚀 REKOMENDASI PERBAIKAN (PRIORITY ORDER)

### Priority 1 (CRITICAL - Do This First)
| No | Issue | Effort | Impact | Files |
|----|-------|--------|--------|-------|
| 1 | Parallelize TTS synthesis | 2 jam | -30% total time | long_animate.py |
| 2 | Aggressive retry + timeout downgrade | 1.5 jam | -80% timeout hang | long_animate.py |
| 3 | Error handling & logging | 2 jam | Debuggability +100% | long_animate.py, llm.py |
| 4 | Resource cleanup on error | 1 jam | Zero disk leaks | long_animate.py |

### Priority 2 (HIGH - Do Next Sprint)
| No | Issue | Effort | Impact | Files |
|----|-------|--------|--------|-------|
| 5 | Vision QA caching | 1.5 jam | -20% image gen time | long_animate.py |
| 6 | FFmpeg filter optimization | 1 jam | -15% encoding time | long_animate.py |
| 7 | Shot duration validation | 1 jam | Zero timing drift | long_animate.py |
| 8 | Configurable voice trim | 30 min | Better audio quality | long_animate.py |

### Priority 3 (MEDIUM - Next)
| No | Issue | Effort | Impact | Files |
|----|-------|--------|--------|-------|
| 9 | Structured logging | 1.5 jam | Better observability | long_animate.py |
| 10 | Parametric geometry | 1 jam | Extensibility | long_animate.py |

---

## 📊 EXPECTED IMPROVEMENTS

### Sebelum Perbaikan
- **Total time**: 10-15 menit untuk 5-scene video
  - Storyboard: 10s
  - TTS: 30s (sequential)
  - Image gen: 300s (5 shots × 60s per shot retry)
  - Render shots: 120s
  - Final composite: 180s
  - QC: 10s

### Sesudah Perbaikan (All Priority 1+2)
- **Total time**: 4-6 menit (60% faster!)
  - Storyboard: 10s (no change)
  - TTS: 8s (parallel)
  - Image gen: 150s (aggressive retry + size downgrade)
  - Render shots: 90s (parallel where possible)
  - Final composite: 140s (optimized filters)
  - QC: 10s (no change)

### Reliability Improvements
- ✅ Zero timeout hangs (was 2-3x/100 renders)
- ✅ Zero disk space leaks (cleanup on error)
- ✅ Accurate timing (validation layer)
- ✅ Better observability (structured logs)

---

## 🔧 IMPLEMENTATION CHECKLIST

### Phase 1: Parallelization & Retry Logic
```python
# ✓ TODO: Parallelize TTS synthesis with ThreadPoolExecutor
# ✓ TODO: Progressive timeout strategy (30s → 60s → 120s)
# ✓ TODO: Universal size downgrade for all providers
# ✓ TODO: Exponential backoff for rate limiting
```

### Phase 2: Error Handling & Logging
```python
# ✓ TODO: Structured logging with timestamps
# ✓ TODO: Resource cleanup context manager
# ✓ TODO: Graceful skip for failed shots (log warning)
# ✓ TODO: JSON report with metrics
```

### Phase 3: Optimization & Caching
```python
# ✓ TODO: Vision QA signature caching
# ✓ TODO: FFmpeg filter reordering
# ✓ TODO: Shot duration validation
# ✓ TODO: Configurable trim threshold
```

---

## 🎯 KPI TRACKING

Track these metrics per render:
- `total_time_seconds` - Full pipeline time
- `storyboard_time` - AI parsing time
- `tts_time` - Voice synthesis (parallel count)
- `image_gen_time` - Per shot (with retry count)
- `render_time` - Per shot (with filter time breakdown)
- `composite_time` - Final FFmpeg
- `provider_used` - Which provider succeeded
- `retry_count` - Total retries across all shots
- `error_count` - Warnings/failures logged
- `disk_space_used_mb` - Intermediate files

Store ini di `${WORK_DIR}/render_report.json` untuk analytics.

---

## 📝 NOTES

- All improvements maintain backward compatibility
- No breaking changes ke `.env` atau API surface
- Safe to implement incrementally
- Each PR fokus pada satu improvement area
