"""The exact eleven /yt-* skills are applied and callable without side effects."""
import pytest

import yt_skills


EXPECTED = ['yt-script', 'yt-package', 'yt-edit', 'yt-comment', 'yt-plan', 'yt-viral',
            'yt-retention', 'yt-shorts', 'yt-seo', 'yt-chapters', 'yt-audit']


def test_all_eleven_requested_skills_are_applied():
    result = yt_skills.snapshot()
    assert result['version'] == yt_skills.VERSION
    assert result['total'] == result['applied'] == 11
    assert [row['id'] for row in result['skills']] == EXPECTED
    assert all(row['applied'] and row['name'] for row in result['skills'])


def test_script_and_package_skill_outputs():
    script = yt_skills.run('yt-script', {'topic': 'cara anak menjaga kejujuran di sekolah'})
    assert script['stages'] and script['title'] and script['source'] == 'template_storyboard'
    package = yt_skills.run('yt-package', {'title': 'Judul video', 'description': 'Penjelasan singkat yang aman.',
                                           'tags': ['anak', 'sekolah']})
    assert package['title'] and package['tags'] == ['anak', 'sekolah']


def test_edit_retention_chapters_and_audit_are_bounded_and_do_not_fabricate():
    stages = [{'text': 'satu dua tiga empat lima enam tujuh delapan sembilan sepuluh'} for _ in range(3)]
    edit = yt_skills.run('yt-edit', {'stages': stages})
    assert edit['total_seconds'] == 60 and len(edit['stage_seconds']) == 3
    retention = yt_skills.run('yt-retention', {'stages': stages})
    assert retention['measured'] is False
    chapters = yt_skills.run('yt-chapters', {'stage_seconds': [10, 20], 'titles': ['Pertanyaan', 'Jawaban']})
    assert [row['start'] for row in chapters['chapters']] == [0, 10]
    held = yt_skills.run('yt-audit', {'checks': {'qc_pass': True}})
    assert held['verdict'] == 'hold' and held['publication_allowed'] is False
    ready = yt_skills.run('yt-audit', {'checks': dict(qc_pass=True, media_integrity=True, rights=True,
        context_safe=True, remote_identity_confirmed=True)})
    assert ready['verdict'] == 'ready' and ready['publication_allowed'] is True


def test_comment_plan_viral_shorts_and_seo_respect_guards():
    assert yt_skills.run('yt-comment', {'question': 'Bagaimana cara mulai?'} )['engagement_bait'] is False
    assert yt_skills.run('yt-viral', {'topic': 'kebiasaan membaca anak sekolah'})['views_guaranteed'] is False
    shorts = yt_skills.run('yt-shorts', {'topic': 'merapikan meja setelah belajar'})
    assert shorts['format'] == 'short' and shorts['max_seconds'] == 55
    assert yt_skills.run('yt-seo', {'topic': 'belajar sejarah dengan cerita'})['keywords']
    plan = yt_skills.run('yt-plan', {})
    assert plan['catch_up'] is False and plan['quota']['weekly_posts'] == 13


@pytest.mark.parametrize('skill_id,payload', [
    ('yt-script', {'topic': ''}), ('yt-package', {'title': 'x', 'description': ''}),
    ('yt-edit', {'stages': []}), ('yt-comment', {'question': 'hubungi https://contoh.com'}),
    ('yt-chapters', {'stage_seconds': [1], 'titles': []}),
    ('yt-audit', {'checks': 'not a dict'}),
])
def test_invalid_inputs_are_rejected(skill_id, payload):
    with pytest.raises(ValueError):
        yt_skills.run(skill_id, payload)


def test_unknown_skill_is_rejected():
    with pytest.raises(ValueError, match='Skill tidak dikenal'):
        yt_skills.run('yt-unknown', {})
