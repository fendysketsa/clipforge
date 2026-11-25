"""Local asset paths inside a clip spec: find them, verify they exist, rewrite them into URLs the local server can serve. Used by render.py (qa.py can copy it verbatim).

Recognized fields (paths are relative to the spec file, absolute paths also work; data: / http(s): pass through untouched):
  cues[].image                 one image (a screenshot, photo, or a frame of footage)
  cues[].frames                frame sequence: a directory (sorted by filename, taking .png/.jpg/.jpeg/.webp) or an array of paths; pair with cues[].fps (default 30)
  data.image                   a syntax-level image (y1 uses it as the centerpiece image)
  data.character               y4 character: a preset name (neutral / bun / author) passes through untouched (y4 retired code-drawn characters and errors at startup asking for a frame library); a directory → frame library (filename without extension = pose name);
                               an object {frames: {pose: path} | directory} behaves the same way
A missing file → FileNotFoundError (the caller refuses to render rather than emit blank frames).
"""
import urllib.parse
from pathlib import Path

FRAME_EXT = ('.png', '.jpg', '.jpeg', '.webp')
PRESETS = ('neutral', 'bun', 'author')


def _perform_url(f, allowed):
    allowed.add(str(f))
    return '/__file__/' + urllib.parse.quote(str(f))


def _perform_file(v, base, allowed, what):
    if not v or str(v).startswith(('data:', 'http:', 'https:')):
        return v
    f = (base / v).resolve()
    if not f.is_file():
        raise FileNotFoundError(f'{what} in spec does not exist: {v} (relative to {base})')
    return _perform_url(f, allowed)


def _perform_dir_frames(v, base, what):
    record_map = (base / v).resolve()
    if not record_map.is_dir():
        return None
    file_entries = sorted(input_path for input_path in record_map.iterdir() if input_path.suffix.lower() in FRAME_EXT)
    if not file_entries:
        raise FileNotFoundError(f'{what} directory in spec is empty (no {"/".join(FRAME_EXT)}): {v}')
    return file_entries


def localize_spec_paths(spec, base, allowed):
    """Rewrite the spec in place. base = directory containing the spec; allowed collects the absolute paths that may be served."""
    base = Path(base)
    for query_value in spec.get('cues', []):
        if query_value.get('image'):
            query_value['image'] = _perform_file(query_value['image'], base, allowed, 'image')
        fr = query_value.get('frames')
        if isinstance(fr, str):
            file_entries = _perform_dir_frames(fr, base, 'frame sequence')
            if file_entries is None:
                raise FileNotFoundError(f'frame sequence directory in spec does not exist: {fr} (relative to {base})')
            query_value['frames'] = [_perform_url(f, allowed) for f in file_entries]
        elif isinstance(fr, list):
            if not fr:
                raise FileNotFoundError('frames in spec is an empty array')
            query_value['frames'] = [_perform_file(v, base, allowed, 'video frame') for v in fr]
    data = spec.get('data') or {}
    if data.get('image'):
        data['image'] = _perform_file(data['image'], base, allowed, 'image')
    ch = data.get('character')
    if isinstance(ch, str) and ch not in PRESETS:
        file_entries = _perform_dir_frames(ch, base, 'character frame library')
        if file_entries is None:
            raise FileNotFoundError(f'data.character is neither a preset ({" / ".join(PRESETS)}) nor a frame library directory: {ch} (relative to {base})')
        data['character'] = {'frames': {f.stem: _perform_url(f, allowed) for f in file_entries}}
    elif isinstance(ch, dict):
        fr = ch.get('frames')
        if isinstance(fr, str):
            file_entries = _perform_dir_frames(fr, base, 'character frame library')
            if file_entries is None:
                raise FileNotFoundError(f'data.character.frames directory does not exist: {fr} (relative to {base})')
            ch['frames'] = {f.stem: _perform_url(f, allowed) for f in file_entries}
        elif isinstance(fr, dict):
            ch['frames'] = {k: _perform_file(v, base, allowed, f'character frame "{k}"') for k, v in fr.items()}
    return spec
