#!/usr/bin/env python3
"""Optional voice configuration. status/resolve never touch the network; personal config lives outside the skill install directory."""
import argparse
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    sys.modules.setdefault("capabilities", sys.modules[__name__])


class ConfigError(ValueError):
    pass


def perform_config_path(explicit_flag=None):
    if explicit_flag:
        return Path(explicit_flag).expanduser().resolve()
    if os.getenv('PULUPULU_CONFIG_HOME'):
        return Path(os.environ['PULUPULU_CONFIG_HOME']).expanduser() / 'media.json'
    if os.name == 'nt':
        return Path(os.environ.get('APPDATA', Path.home() / 'AppData/Roaming')) / 'pulupulu-motion/media.json'
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'pulupulu-motion/media.json'


def read_json_document(path, missing=False):
    if missing and not path.exists():
        return {}
    try:
        raw_payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        raise ConfigError(f'Cannot read config: {path.name} ({type(e).__name__})') from None
    if not isinstance(raw_payload, dict):
        raise ConfigError('config must be a JSON object')
    return raw_payload


def combine(base_folder, apply_patch):
    outcome_payload = copy.deepcopy(base_folder)
    for key, current_value_x in apply_patch.items():
        outcome_payload[key] = combine(outcome_payload[key], current_value_x) if isinstance(current_value_x, dict) and isinstance(outcome_payload.get(key), dict) else copy.deepcopy(current_value_x)
    return outcome_payload


def verify(raw_payload, schema=None, where='config'):
    # This package's schema only uses the JSON Schema keywords below; it does not claim to implement a general schema interpreter.
    schema = schema or read_json_document(ROOT / 'schemas/media.schema.json')
    type_list = {'object': dict, 'string': str, 'integer': int, 'boolean': bool}
    typ_value = schema.get('type')
    if typ_value and (not isinstance(raw_payload, type_list[typ_value]) or (typ_value == 'integer' and isinstance(raw_payload, bool))):
        raise ConfigError(f'{where} has the wrong type')
    if 'enum' in schema and raw_payload not in schema['enum']:
        raise ConfigError(f'{where} is not a supported option')
    if isinstance(raw_payload, int) and not isinstance(raw_payload, bool):
        if raw_payload < schema.get('minimum', raw_payload) or raw_payload > schema.get('maximum', raw_payload):
            raise ConfigError(f'{where} is out of range')
    if isinstance(raw_payload, str) and 'pattern' in schema and not re.fullmatch(schema['pattern'], raw_payload):
        raise ConfigError(f'{where} has the wrong format')
    if isinstance(raw_payload, dict):
        for key in schema.get('required', []):
            if key not in raw_payload:
                raise ConfigError(f'{where}.{key} is missing')
        for key, current_value_x in raw_payload.items():
            child_value = schema.get('properties', {}).get(key, schema.get('additionalProperties', False))
            if child_value is False:
                raise ConfigError(f'{where}.{key} is not a supported field')
            if isinstance(child_value, dict):
                verify(current_value_x, child_value, f'{where}.{key}')


def perform_project_patch(raw_payload):
    verify(raw_payload)
    if set(raw_payload) - {'schema_version', 'revision', 'preferences', 'policy', 'onboarding'}:
        raise ConfigError('a project config cannot set credential bindings, network policy or low-level provider parameters')
    if any(v != 'deny' for v in raw_payload.get('policy', {}).values()):
        raise ConfigError('a project policy can only tighten settings to deny; it cannot grant cloud calls, paid usage or training')
    if 'voice_ref' in raw_payload.get('preferences', {}).get('voice', {}):
        raise ConfigError('private voice bindings stay in the user config; pick one for this run with --voice')
    return raw_payload


def effective_value(explicit_flag=None, project=None):
    defaults = read_json_document(ROOT / 'defaults/media.json')
    active_user_path = perform_config_path(explicit_flag)
    user = read_json_document(active_user_path, missing=True)
    verify(user)
    outcome_payload = combine(defaults, user)
    sources = {'defaults': 'defaults/media.json', 'user': str(active_user_path), 'user_configured': bool(user)}
    origin_value = {}
    def note(raw_payload, display_label, prefix=''):
        for key, current_value_x in raw_payload.items():
            name = prefix + key
            if isinstance(current_value_x, dict): note(current_value_x, display_label, name + '.')
            elif name.split('.')[0] in ('preferences', 'policy', 'provider_options', 'onboarding'): origin_value[name] = display_label
    note(defaults, 'public_default'); note(user, 'user')
    if project:
        pixel_pair = Path(project).expanduser().resolve() / '.pulupulu-motion/media.json'
        apply_patch = perform_project_patch(read_json_document(pixel_pair, missing=True))
        outcome_payload = combine(outcome_payload, apply_patch)
        note(apply_patch, 'project')
        sources['project'] = str(pixel_pair)
        sources['project_fields'] = sorted(apply_patch)
    verify(outcome_payload)
    sources['effective_from'] = origin_value
    return outcome_payload, sources


@contextmanager
def locked_flag(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    active_lock_path = path.with_name(path.name + '.lock')
    # The kernel file lock is released when the process exits; ownership is never fought over by deleting the lock file.
    with active_lock_path.open('a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            if lock.seek(0, 2) == 0:
                lock.write(b'0'); lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)


def write_patch(path, apply_patch, expected=None, reset=None):
    verify(apply_patch)
    with locked_flag(path):
        previous_value = read_json_document(path, missing=True)
        verify(previous_value)
        revision = previous_value.get('revision', 0)
        if expected is not None and revision != expected:
            raise ConfigError('the config was modified by another process; re-read it and try again')
        updated_flag = combine(previous_value, apply_patch)
        if reset:
            # Only public fields may be reset; no dynamic path expressions are evaluated.
            key_list = reset.split('.')
            if key_list[0] not in {'preferences', 'policy', 'bindings', 'provider_options', 'onboarding'}:
                raise ConfigError('unsupported reset path')
            current_value = updated_flag
            for key in key_list[:-1]:
                current_value = current_value.get(key, {})
            if isinstance(current_value, dict):
                current_value.pop(key_list[-1], None)
        updated_flag.update(schema_version=1, revision=revision + 1)
        verify(updated_flag)
        stream_handle, scratch_path = tempfile.mkstemp(dir=path.parent, prefix='.media-')
        try:
            with os.fdopen(stream_handle, 'w', encoding='utf-8') as f:
                json.dump(updated_flag, f, ensure_ascii=False, indent=2); f.write('\n')
            if os.name != 'nt':
                os.chmod(scratch_path, 0o600)
            os.replace(scratch_path, path)
        finally:
            if os.path.exists(scratch_path):
                os.unlink(scratch_path)
        return {'status': 'saved', 'revision': updated_flag['revision'], 'path': str(path)}


def credentials(config):
    binding = config['bindings']['volcengine']
    entry_names = (binding['appid_env'], binding['token_env'])
    values = {n: os.getenv(n) for n in entry_names}
    active_env_path = os.getenv('KOUBO_ENV') or binding.get('env_file')
    if active_env_path and not all(values.values()):
        path = Path(active_env_path).expanduser()
        if path.is_file():
            for source_line in path.read_text(encoding='utf-8').splitlines():
                source_line = source_line.strip()
                if source_line.startswith('export '):
                    source_line = source_line[7:]
                key, separator_text, current_value_x = source_line.partition('=')
                if separator_text and key.strip() in entry_names and not values[key.strip()]:
                    values[key.strip()] = current_value_x.strip().strip('\"\'')
    return tuple(values[n] for n in entry_names)


def speaker(config, explicit_flag=None):
    reference_value = explicit_flag or config['preferences']['voice'].get('voice_ref', 'default')
    voice = config['bindings']['voices'].get(reference_value)
    if voice and voice.get('speaker_id'):
        return voice['speaker_id']
    if explicit_flag and not voice:
        # Compatible with the registry aliases and platform IDs of older commands.
        voice = {'entry': explicit_flag}
    voice = voice or {'entry': 'default'}
    active_registry_path = Path(voice.get('registry_file') or config['bindings']['volcengine']['registry_file']).expanduser()
    registry_value = read_json_document(active_registry_path, missing=True)
    entry = voice.get('entry', 'default')
    if entry == 'default':
        entry = registry_value.get('default') or os.getenv('VOLC_KOUBO_DEFAULT_SPEAKER')
    found = registry_value.get('voices', {}).get(entry, {})
    return found.get('speaker_id') or (entry if isinstance(entry, str) and entry.startswith('S_') else None)


def resolve(config, mode=None, audio=None, operation='synthesize', grants=(), voice=None):
    chosen_option = mode or config['preferences']['voice']['mode']
    if audio and mode is None:
        chosen_option = 'provided'
    outcome_payload = {'capability': 'voice', 'mode': chosen_option, 'operation': operation, 'status': 'ready', 'reasons': []}
    if chosen_option == 'off':
        return dict(outcome_payload, status='skipped', reasons=['voice is disabled; no audio will be generated'])
    if chosen_option == 'unconfigured':
        return dict(outcome_payload, status='needs_configuration', prompt=config['onboarding']['voice'] != 'manual',
                    reasons=['pick an existing recording, a system voice or an already-bound cloned voice; you can also skip it for this run'])
    if chosen_option == 'provided':
        if not audio or not Path(audio).expanduser().is_file():
            return dict(outcome_payload, status='needs_input', reasons=['a path to existing audio is required'])
        return outcome_payload
    if chosen_option == 'system':
        missing = [sample_value for sample_value in ('say', 'ffmpeg', 'ffprobe') if not shutil.which(sample_value)]
        if platform.system() != 'Darwin' or missing:
            return dict(outcome_payload, status='unavailable', reasons=['the system voice only works on macOS for now and needs say/ffmpeg/ffprobe installed'])
        return dict(outcome_payload, provider='macos')
    if chosen_option != 'clone':
        raise ConfigError('unsupported voice mode')
    outcome_payload['provider'] = 'volcengine'
    if config['preferences']['voice'].get('provider', 'volcengine') != 'volcengine':
        return dict(outcome_payload, status='unavailable', reasons=['the P1 clone backend only supports volcengine'])
    needs = ['cloud'] + ([] if operation == 'check' else ['paid_api'])
    if operation == 'train':
        needs.append('voice_training')
    denied = [key for key in needs if config['policy'][key] == 'deny']
    if denied:
        return dict(outcome_payload, status='blocked', reasons=['explicitly denied: ' + ', '.join(denied)])
    pending_flag = [key for key in needs if config['policy'][key] != 'allow' and key not in grants]
    if pending_flag:
        return dict(outcome_payload, status='needs_permission', reasons=['needs a grant for this run: ' + ', '.join(pending_flag)])
    application_id, auth_token = credentials(config)
    if not application_id or not auth_token:
        outcome_payload['reasons'].append('missing credentials for the selected provider; only the given environment/credential files were checked')
    if operation == 'synthesize' and not speaker(config, voice):
        outcome_payload['reasons'].append('no usable voice binding; you can bind an existing ID, no retraining needed')
    missing = [sample_value for sample_value in ('ffmpeg', 'ffprobe') if not shutil.which(sample_value)]
    if missing:
        outcome_payload['reasons'].append('missing local dependencies: ' + ', '.join(missing))
    import importlib.util
    if importlib.util.find_spec('requests') is None:
        outcome_payload['reasons'].append('the volcengine adapter needs requests; basic config and existing audio do not')
    outcome_payload['status'] = 'unavailable' if outcome_payload['reasons'] else 'configured_unverified'
    return outcome_payload


def probe_sound_track(path):
    if not shutil.which('ffprobe'):
        raise ConfigError('audio acceptance needs ffprobe')
    proc_value = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                           'stream=codec_type,codec_name,sample_rate,channels:format=duration', '-of', 'json', str(path)],
                          capture_output=True, text=True)
    if proc_value.returncode:
        raise ConfigError('the output is not decodable audio')
    raw_payload = json.loads(proc_value.stdout)
    streams = [s for s in raw_payload.get('streams', []) if s.get('codec_type') == 'audio']
    duration = float(raw_payload.get('format', {}).get('duration', 0))
    if not streams or duration <= 0:
        raise ConfigError('the output has no valid audio stream or duration')
    return {'duration': duration, **streams[0], 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def perform_system_voice_for(text, configured_flag=None):
    if configured_flag:
        return configured_flag
    # The macOS default English voice can return near-silent audio for Chinese; only pick from installed voices, never download.
    if re.search(r"[\u4e00-\u9fff]", text):
        outcome_payload = subprocess.run(['say', '-v', '?'], capture_output=True, text=True, check=True)
        entry_names = [matched_object.group(1).strip() for source_line in outcome_payload.stdout.splitlines()
                 if (matched_object := re.match(r"(.+?)\s+zh_CN\s+#", source_line))]
        if not entry_names:
            raise ConfigError('no Mandarin system voice is installed; pick an existing voice or import a recording')
        return 'Tingting' if 'Tingting' in entry_names else entry_names[0]
    return None


def execute_say(cli_options, config):
    grants = [name for name in ('cloud', 'paid_api') if getattr(cli_options, 'allow_' + name, False)]
    outcome_payload = resolve(config, mode=cli_options.mode, grants=grants, voice=cli_options.voice)
    if outcome_payload['status'] not in ('ready', 'configured_unverified'):
        print(json.dumps(outcome_payload, ensure_ascii=False)); raise SystemExit(2)
    if not cli_options.text.strip():
        raise ConfigError('synthesis text must not be empty')
    out = Path(cli_options.out).expanduser()
    if out.exists():
        raise ConfigError('the output file already exists; name a new file and keep the selected track')
    if cli_options.speech_rate is not None and not -50 <= cli_options.speech_rate <= 100:
        raise ConfigError('volcengine speech rate must be between -50 and 100')
    if cli_options.fit is not None and cli_options.fit <= 0:
        raise ConfigError('--fit must be a positive number')
    if cli_options.match and not Path(cli_options.match).is_file():
        raise ConfigError('loudness reference audio not found')
    requested_format_value = cli_options.format
    out.parent.mkdir(parents=True, exist_ok=True)
    import koubo
    # A temp workspace keeps a failure or a half-finished response from polluting the final artifact.
    with tempfile.TemporaryDirectory(prefix='voice-', dir=out.parent) as scratch_path:
        staged_value = Path(scratch_path) / (out.name + '.wav' if requested_format_value == 'pcm' else out.name)
        if outcome_payload['mode'] == 'system':
            if cli_options.model or cli_options.speech_rate is not None or cli_options.no_fidelity:
                raise ConfigError('volcengine model/speech-rate parameters do not apply to the system voice')
            if cli_options.format != 'wav' or cli_options.sample_rate != 48000:
                raise ConfigError('P1 system-voice output is fixed at 48kHz WAV')
            source_value = Path(scratch_path) / 'system.aiff'
            subcommand_name = ['say', '-o', str(source_value)]
            system_voice = perform_system_voice_for(cli_options.text, cli_options.voice or config['preferences']['voice'].get('system_voice'))
            if system_voice:
                subcommand_name += ['-v', system_voice]
            subprocess.run(subcommand_name, input=cli_options.text, text=True, check=True, capture_output=True)
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(source_value), '-ar', '48000', str(staged_value)], check=True)
            if cli_options.fit:
                koubo.fit_duration(staged_value, cli_options.fit)
            target_db_value = koubo.mean_volume(cli_options.match, cli_options.match_ss, cli_options.match_t) if cli_options.match else cli_options.loudness
            if target_db_value is not None:
                koubo.match_loudness(staged_value, target_db_value)
        else:
            koubo.configure_backend(config)
            cli_options = copy.copy(cli_options)
            cli_options.out = str(staged_value)
            # Validate fit / loudness / termination state on the containerised audio first, then export raw PCM.
            if requested_format_value == 'pcm': cli_options.format = 'wav'
            cli_options.voice = speaker(config, cli_options.voice)
            chosen_options = config['provider_options']['volcengine']
            cli_options.model = cli_options.model or chosen_options['model']
            from voice_review import review_status
            print(json.dumps({'model_review': review_status('volcengine', cli_options.model, getattr(cli_options, 'config', None))}, ensure_ascii=False), file=sys.stderr)
            cli_options.speech_rate = chosen_options['speech_rate'] if cli_options.speech_rate is None else cli_options.speech_rate
            cli_options.no_fidelity = not chosen_options['tone_fidelity'] if cli_options.no_fidelity is None else cli_options.no_fidelity
            koubo.cmd_say(cli_options)
        artifact = probe_sound_track(staged_value)
        volume_value = koubo.mean_volume(staged_value)
        if artifact['duration'] < 0.12 or volume_value is None or volume_value < -60:
            raise ConfigError('synthesized audio is near-silent or has no usable sound; not accepted as a successful artifact')
        if cli_options.fit and abs(artifact['duration'] - cli_options.fit) > .05:
            # Keep the diagnostic candidate, but never treat it as a valid final output.
            candidate = out.with_name(out.stem + '.unfitted' + out.suffix)
            if not candidate.exists():
                shutil.copy2(staged_value, candidate)
            raise ConfigError('audio did not land within ±0.05s of the target duration; the unfitted candidate was kept and not delivered as final audio')
        if requested_format_value == 'pcm':
            raw_payload_x = Path(scratch_path) / 'output.pcm'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(staged_value), '-ac', '1', '-ar', str(cli_options.sample_rate), '-f', 's16le', str(raw_payload_x)], check=True)
            shutil.copy2(raw_payload_x, out)
            artifact.update(format='s16le', channels=1, duration=out.stat().st_size / 2 / cli_options.sample_rate, sha256=hashlib.sha256(out.read_bytes()).hexdigest())
        else:
            shutil.copy2(staged_value, out)
    artifact.update(path=out.name, provider=outcome_payload['provider'], mode=outcome_payload['mode'], generated=True)
    if outcome_payload['mode'] == 'system':
        artifact['system_voice'] = system_voice or 'system_default'
    if outcome_payload['mode'] == 'clone':
        artifact['requested_model'] = cli_options.model
    out.with_name(out.name + '.json').write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'complete', 'output': str(out), 'duration': artifact['duration']}, ensure_ascii=False))


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ('image-status', 'image-plan', 'accept-image', 'use-image'):
        import images
        return images.main()
    # Generation/training commands reuse the original CLI so two sets of parameters cannot drift apart.
    if len(sys.argv) > 1 and sys.argv[1] in ('say', 'train', 'voices'):
        import koubo
        return koubo.main()
    argument_parser = argparse.ArgumentParser(description=__doc__)
    segment_record = argument_parser.add_subparsers(dest='command', required=True)
    for name in ('status', 'resolve', 'configure', 'skip', 'reset', 'bind', 'use-audio'):
        input_path = segment_record.add_parser(name)
        input_path.add_argument('--config')
        input_path.add_argument('--project')
        if name in ('status', 'resolve'):
            input_path.add_argument('--mode', choices=['off', 'provided', 'system', 'clone'])
            input_path.add_argument('--audio'); input_path.add_argument('--explain', action='store_true')
        if name == 'configure':
            input_path.add_argument('--input', required=True); input_path.add_argument('--scope', choices=['user', 'project'], default='user')
            input_path.add_argument('--expected-revision', type=int)
        if name == 'skip':
            input_path.add_argument('--capability', choices=['voice', 'image'], default='voice')
            input_path.add_argument('--scope', choices=['task', 'user'], default='task')
        if name == 'reset':
            input_path.add_argument('--field', default='preferences.voice')
        if name == 'bind':
            input_path.add_argument('--name', required=True); input_path.add_argument('--speaker-id', required=True)
            input_path.add_argument('--default', action='store_true')
        if name == 'use-audio':
            input_path.add_argument('--audio', required=True); input_path.add_argument('--out', required=True)
    cli_options = argument_parser.parse_args()
    config, sources = effective_value(cli_options.config, cli_options.project)
    path = perform_config_path(cli_options.config)
    if cli_options.command in ('status', 'resolve'):
        outcome_payload = resolve(config, cli_options.mode, cli_options.audio)
        outcome_payload['revision'] = config.get('revision', 0)
        outcome_payload['parameters'] = config['provider_options']['volcengine'] if outcome_payload.get('provider') == 'volcengine' else {}
        if outcome_payload.get('provider') == 'volcengine':
            from voice_review import review_status
            outcome_payload['model_review'] = review_status('volcengine', outcome_payload['parameters']['model'], path)
        if cli_options.explain:
            outcome_payload['sources'] = sources
        print(json.dumps(outcome_payload, ensure_ascii=False, indent=2))
    elif cli_options.command == 'configure':
        apply_patch = read_json_document(Path(cli_options.input))
        if cli_options.scope == 'project':
            if not cli_options.project:
                raise ConfigError('project scope requires --project')
            path = Path(cli_options.project).expanduser().resolve() / '.pulupulu-motion/media.json'
            perform_project_patch(apply_patch)
        print(json.dumps(write_patch(path, apply_patch, cli_options.expected_revision), ensure_ascii=False))
    elif cli_options.command == 'skip':
        if cli_options.scope == 'user':
            print(json.dumps(write_patch(path, {'onboarding': {cli_options.capability: 'manual'}, 'preferences': {cli_options.capability: {'mode': 'unconfigured'}}}), ensure_ascii=False))
        else:
            print(json.dumps({'status': 'skipped', 'scope': 'task', 'saved': False}, ensure_ascii=False))
    elif cli_options.command == 'reset':
        print(json.dumps(write_patch(path, {}, reset=cli_options.field), ensure_ascii=False))
    elif cli_options.command == 'bind':
        apply_patch = {'bindings': {'voices': {cli_options.name: {'speaker_id': cli_options.speaker_id}}}}
        if cli_options.default:
            apply_patch['preferences'] = {'voice': {'voice_ref': cli_options.name}}
        print(json.dumps(write_patch(path, apply_patch), ensure_ascii=False))
    elif cli_options.command == 'use-audio':
        source_value, out = Path(cli_options.audio).expanduser(), Path(cli_options.out).expanduser()
        info_map = probe_sound_track(source_value)
        if out.exists():
            raise ConfigError('the output already exists; name a new file')
        out.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source_value, out)
        info_map.update(path=out.name, generated=False, mode='provided')
        out.with_name(out.name + '.json').write_text(json.dumps(info_map, ensure_ascii=False, indent=2))
        print(json.dumps({'status': 'complete', 'output': str(out), 'generated': False}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ConfigError, OSError, subprocess.SubprocessError) as e:
        message = str(e) if isinstance(e, ConfigError) else type(e).__name__
        print(json.dumps({'status': 'error', 'message': message}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
