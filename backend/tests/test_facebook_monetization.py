from pathlib import Path
from types import SimpleNamespace
import json

from fastapi.testclient import TestClient
import pytest
import api
import facebook_api
import facebook_monetization as mon


def pages():
    return {
        'overview':'Belum memenuhi syarat\nLangganan\nStatus monetisasi\nProfil Anda menghasilkan uang\nBagus! Konten profil Anda menghasilkan uang.',
        'content':'Pendapatan monetisasi konten\nPendapatan November\n$0.00\nPerkiraan pendapatan\nBonuses\nDapatkan bonus US$1\nBuat 3 reel, semuanya berdurasi 10 detik atau lebih, dan capai 10 tayangan yang memenuhi syarat di setidaknya 1 reel\n0/3 reel yang memenuhi syarat · 5 hari tersisa',
        'rate':'$0.00\nTingkat pendapatan\nPer 1.000 tayangan yang memenuhi syarat\n0\nTayangan yang memenuhi syarat\nDurasi tayangan terlalu singkat\n98%\nDurasi konten kurang dari 10 detik\n2%',
        'health':'Status akun\nTidak ada batasan\nRekomendasi\nAktif\nMonetisasi\nAktif',
        'insights':'28 hari terakhir: 18 Okt - 14 Nov\n91\n-79%\nTayangan\n5\n-97%\nTayangan 3 detik',
        'bonus_detail':'Detail bonus\n12 Nov - 19 Nov\nDapatkan bonus US$1',
    }


def test_account_active_does_not_mean_views_qualified_or_payout_ready():
    result=mon.parse_pages(pages(),account_verified=True)
    assert result['program']['state']=='active'
    assert result['policy']['state']=='clear'
    assert result['earnings']['qualified_views']==0
    assert result['earnings']['estimated_usd']==0
    assert result['earnings']['non_qualified_reasons'][0]['percent']==98
    assert result['payout']['state']=='unknown'
    assert result['insights']['views']==91
    assert result['insights']['three_second_views']==5


def test_bonus_progress_is_not_derived_from_local_upload_counts():
    result=mon.parse_pages(pages(),account_verified=True)
    bonus=result['bonus']
    assert bonus['completed_reels']==0 and not bonus['awarded']
    assert bonus['required_reels']==3 and bonus['minimum_duration_seconds']==10
    assert bonus['minimum_qualified_views']==10 and bonus['minimum_reels_with_qualified_views']==1
    assert bonus['period_label']=='12 Nov - 19 Nov'
    assert bonus['days_remaining_at_check']==5


def test_missing_views_are_unknown_and_not_fabricated_zero():
    result=mon.parse_pages({'content':'Halaman Ini Tidak Tersedia'},account_verified=True)
    assert result['earnings']['qualified_views'] is None
    assert result['earnings']['estimated_usd'] is None
    assert result['earnings']['rate_usd_per_1000'] is None
    assert result['program']['state']=='unknown'
    assert result['bonus'] is None


def test_unverified_account_cannot_supply_positive_monetization_evidence():
    result=mon.parse_pages(pages(),account_verified=False)
    assert result['program']['state']=='unknown'
    assert result['policy']['state']=='unknown'
    assert result['earnings']['qualified_views'] is None
    assert result['earnings']['estimated_usd'] is None
    assert result['bonus'] is None


def test_explicit_restriction_overrides_generic_active_status():
    value=pages();value['health']='Monetisasi dinonaktifkan'
    result=mon.parse_pages(value,account_verified=True)
    assert result['program']['state']=='restricted'
    assert result['policy']['state']=='restricted'


@pytest.mark.parametrize('text',[
    'Pembayaran berikutnya $0.00',
    'Formulir pajak\nCondro, dapatkan lencana terverifikasi\nDaftar untuk Verifikasi Meta',
    'Bantuan pembayaran\nPerlu bantuan untuk memulai?',
])
def test_payment_balance_and_meta_verified_upsell_are_not_payout_approval(text):
    assert mon.payout_status(text)['state']=='unknown'


def test_payment_status_does_not_persist_bank_or_tax_details():
    text='Set up payouts\nBank rahasia 1234567890\nTax ID 99887766\nowner@example.test'
    result=mon.payout_status(text)
    assert result['state']=='action_required'
    assert not any(value in json.dumps(result) for value in ['1234567890','99887766','owner@example.test','Bank rahasia'])


def test_payment_issue_overrides_ready_phrase():
    result=mon.payout_status('Payouts are active. Pembayaran ditahan. Verify your identity.')
    assert result['state']=='action_required'


@pytest.mark.parametrize('raw,expected',[('0.00',0),('1,234.56',1234.56),('1.234,56',1234.56),('0,25',.25)])
def test_money_formats_do_not_inflate_amounts(raw,expected):
    assert mon.amount(raw)==expected


def test_qualified_views_with_thousands_separator_remain_an_integer():
    value=pages();value['rate']=value['rate'].replace('\n0\nTayangan','\n1.234\nTayangan')
    assert mon.parse_pages(value,account_verified=True)['earnings']['qualified_views']==1234


def test_briefs_require_original_media_and_do_not_pretend_to_be_finished_clips():
    rows=mon.briefs()
    assert len(rows)==3 and len({row['key'] for row in rows})==3
    assert all(row['state']=='needs_original_recording' and row['max_seconds']==55 for row in rows)
    assert all('http' not in row['caption'] and 'Sumber' not in row['caption'] for row in rows)
    job=SimpleNamespace(request=SimpleNamespace(facebook_source_rights='permission_no_credit',confirm_source_rights=True))
    assert mon.clip_assessment(job)['state']=='facebook_review_required'


def test_unknown_snapshot_api_does_not_seed_screenshot_as_a_live_account_status():
    result=TestClient(api.app).get('/api/facebook/monetization').json()
    assert result['program']['state']=='unknown'
    assert result['checked_at'] is None
    assert result['earnings']['qualified_views'] is None


def test_refresh_is_single_flight_and_keeps_existing_upload_ledger(monkeypatch):
    calls=[]
    monkeypatch.setattr(facebook_api,'start_background',lambda *args:calls.append(args))
    client=TestClient(api.app)
    before=client.get('/api/facebook/uploads').json()
    first=client.post('/api/facebook/monetization/check').json()
    second=client.post('/api/facebook/monetization/check').json()
    assert first['check_state']==second['check_state']=='running'
    assert len(calls)==1
    assert client.get('/api/facebook/uploads').json()==before


def test_read_failure_keeps_last_dated_snapshot_and_does_not_claim_logout(monkeypatch):
    monkeypatch.setattr(api,'social_upload_turn',__import__('contextlib').nullcontext)
    monkeypatch.setattr(mon,'collect',lambda _:(_ for _ in ()).throw(ConnectionError('offline')))
    monkeypatch.setattr(facebook_api,'start_background',lambda target,*args:target(*args))
    path=api.JOBS_PATH.parent/'facebook_workspace.json'
    snapshot=mon.parse_pages(pages(),account_verified=True,checked_at='2026-11-15T01:00:00+00:00')
    path.write_text(json.dumps({'schema':1,'uploads':{},'session':{'verified_profile_id':'1234'},'monetization':snapshot}))
    client=TestClient(api.app)
    client.post('/api/facebook/monetization/check')
    result=client.get('/api/facebook/monetization').json()
    assert result['check_state']=='failed'
    assert result['checked_at']=='2026-11-15T01:00:00+00:00'
    assert result['program']['state']=='active'
    assert result['earnings']['qualified_views']==0
