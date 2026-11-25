import hashlib
import io
import json
import urllib.error
import urllib.request

import pytest

import api


PRIMARY = 'primary-test-key'
BACKUP = 'backup-test-key'


def _quota_error():
    body = json.dumps({'error': {'message': 'quota', 'errors': [{'reason': 'quotaExceeded'}]}}).encode()
    return urllib.error.HTTPError('https://example.invalid', 429, 'Too Many Requests', None, io.BytesIO(body))


def _setup_keys(monkeypatch):
    monkeypatch.setenv('YOUTUBE_DATA_API_KEY', PRIMARY)
    monkeypatch.setenv('YOUTUBE_DATA_API_KEYS', f'{BACKUP}, {PRIMARY}')
    monkeypatch.setattr(api, 'youtube_data_api_cache', {})
    monkeypatch.setattr(api, 'youtube_data_api_cache_lock', __import__('threading').Lock())


def test_key_list_keeps_primary_first_and_deduplicates(monkeypatch):
    _setup_keys(monkeypatch)
    assert api.youtube_data_api_keys() == [PRIMARY, BACKUP]


def test_quota_on_primary_fails_over_to_backup(monkeypatch):
    _setup_keys(monkeypatch)
    used = []

    def fake_urlopen(request, timeout=None):
        used.append(request.full_url)
        if len(used) == 1:
            raise _quota_error()
        return io.BytesIO(b'{"items":[{"id":"abc"}]}')

    monkeypatch.setattr(api.urllib.request, 'urlopen', fake_urlopen)
    payload = api.youtube_data_api_get('videos', {'part': 'id', 'id': 'abc'})
    assert payload['items'][0]['id'] == 'abc'
    assert len(used) == 2
    assert 'primary-test-key' in used[0] and 'backup-test-key' in used[1]


def test_cache_is_shared_between_keys(monkeypatch):
    _setup_keys(monkeypatch)
    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append(request.full_url)
        return io.BytesIO(b'{"items":[]}')

    monkeypatch.setattr(api.urllib.request, 'urlopen', fake_urlopen)
    api.youtube_data_api_get('videos', {'part': 'id', 'id': 'shared'})
    api.youtube_data_api_get('videos', {'part': 'id', 'id': 'shared'})
    assert len(calls) == 1


def test_non_quota_error_is_not_retried(monkeypatch):
    _setup_keys(monkeypatch)
    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append(request.full_url)
        raise urllib.error.HTTPError('https://example.invalid', 403, 'Forbidden', None, io.BytesIO(b'{}'))

    monkeypatch.setattr(api.urllib.request, 'urlopen', fake_urlopen)
    with pytest.raises(RuntimeError) as exc:
        api.youtube_data_api_get('videos', {'part': 'id', 'id': 'abc'})
    assert 'HTTP 403' in str(exc.value)
    assert len(calls) == 1


def test_exhausted_quota_names_all_keys_without_leaking_them(monkeypatch):
    _setup_keys(monkeypatch)
    key_ids = [hashlib.sha256(key.encode()).hexdigest()[:10] for key in (PRIMARY, BACKUP)]

    def fake_urlopen(request, timeout=None):
        raise _quota_error()

    monkeypatch.setattr(api.urllib.request, 'urlopen', fake_urlopen)
    with pytest.raises(RuntimeError) as exc:
        api.youtube_data_api_get('videos', {'part': 'id', 'id': 'abc'})
    message = str(exc.value)
    assert 'semua key' in message
    assert all(key_id in message for key_id in key_ids)
    assert PRIMARY not in message and BACKUP not in message
