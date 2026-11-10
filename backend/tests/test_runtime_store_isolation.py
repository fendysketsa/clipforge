"""Tests must not persist synthetic upload records or touch real login state."""
import api


def test_all_upload_stores_and_login_paths_are_isolated(tmp_path):
    for name in ('JOBS_PATH', 'YOUTUBE_UPLOADS_PATH', 'TIKTOK_UPLOADS_PATH',
                 'YOUTUBE_PLAYWRIGHT_STATE', 'TIKTOK_PLAYWRIGHT_STATE'):
        assert getattr(api, name).is_relative_to(tmp_path), name
