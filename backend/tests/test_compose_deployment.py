"""Offline deployment contract tests: Compose graph, immutable builds and state."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

import deployment_runtime as deploy

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture
def project(tmp_path):
    root=tmp_path/'image';root.mkdir()
    for name in ('api.py','telegram_bot.py','cron_long_strategy.py','ryuundy_editorial_themes.py',
                 'requirements.txt','docker-entrypoint.sh','Dockerfile'):
        (root/name).write_text('# deployment fixture\n')
    (root/'remotion/src').mkdir(parents=True)
    (root/'remotion/src/index.jsx').write_text('export const value=1;')
    deploy.build_manifest(root)
    return root


def test_image_manifest_covers_bot_backend_and_renderer(project):
    result=deploy.verify_manifest(project)
    assert {'api.py','telegram_bot.py','cron_long_strategy.py','ryuundy_editorial_themes.py',
            'remotion/src/index.jsx'} <= result['files'].keys()


@pytest.mark.parametrize('change',['edit','add','delete'])
def test_mixed_or_stale_image_is_refused(project,change):
    if change=='edit':(project/'api.py').write_text('value=2')
    if change=='add':(project/'new_feature.py').write_text('value=2')
    if change=='delete':(project/'telegram_bot.py').unlink()
    with pytest.raises(RuntimeError,match='Image source differs'):
        deploy.verify_manifest(project)


def test_source_race_stops_boot_but_mutable_checkpoints_are_ignored(project,tmp_path):
    source=tmp_path/'source';shutil.copytree(project,source)
    (source/'data').mkdir();(source/'data/tiktok_uploads.json').write_text('[{"submission_accepted":true}]')
    assert deploy.verify_manifest(project,source)['schema']==1
    (source/'api.py').write_text('new_code=True')
    with pytest.raises(RuntimeError,match='Source changed'):
        deploy.verify_manifest(project,source)


def test_invalid_python_fails_during_build_before_recreation(project):
    (project/'api.py').write_text('def invalid syntax:')
    with pytest.raises(SyntaxError):deploy.build_manifest(project)


def test_changed_channel_logo_cannot_pass_image_verification(project):
    branding = project / 'assets' / 'branding'
    branding.mkdir(parents=True)
    seal = branding / 'ryuundy-watermark-v2.svg'
    seal.write_text('<svg/>')
    deploy.build_manifest(project)
    seal.write_text('<svg><text>changed logo</text></svg>')
    with pytest.raises(RuntimeError, match='Image source differs'):
        deploy.verify_manifest(project)


def test_prepare_preserves_cron_session_and_upload_checkpoints(project,tmp_path,monkeypatch):
    state=tmp_path/'data';state.mkdir()
    files={'auto_viral_schedule_control.json':'{"enabled":false}',
           'tiktok_uploads.json':'[{"submission_accepted":true}]','youtube_storage_state.json':'{"cookies":[]}'}
    for name,value in files.items():(state/name).write_text(value)
    monkeypatch.setattr(deploy,'ROOT',project)
    monkeypatch.setattr(deploy,'verify_dependencies',lambda:None)
    monkeypatch.setenv('CLIPFORGE_DEPLOYMENT_REPORT_DIR',str(state/'deployment'))
    monkeypatch.setenv('CLIPFORGE_VERIFY_SOURCE_DIR',str(project))
    record=deploy.prepare('backend',['python','-m','uvicorn','api:app'])
    assert record['verified'] and record['source_verified']
    assert all((state/name).read_text()==value for name,value in files.items())


def test_bot_cannot_start_with_another_backend_release(project,tmp_path,monkeypatch):
    monkeypatch.setattr(deploy,'ROOT',project)
    monkeypatch.setenv('CLIPFORGE_DEPLOYMENT_REPORT_DIR',str(tmp_path/'reports'))
    monkeypatch.delenv('CLIPFORGE_VERIFY_SOURCE_DIR',raising=False)
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','test-only-not-a-real-token')
    monkeypatch.setenv('TELEGRAM_OWNER_ID','123')
    deploy.write_json(deploy.report_path('backend'),{'release_id':'different'})
    monkeypatch.setattr(deploy,'backend_contract',lambda *a:{'director_policy':4})
    with pytest.raises(RuntimeError,match='different source'):
        deploy.prepare('telegram-bot',['python','telegram_bot.py'])
    assert not deploy.report_path('telegram-bot').exists()


def test_bot_preparation_requires_verified_frontend(project,tmp_path,monkeypatch):
    monkeypatch.setattr(deploy,'ROOT',project)
    monkeypatch.setenv('CLIPFORGE_DEPLOYMENT_REPORT_DIR',str(tmp_path/'reports'))
    monkeypatch.delenv('CLIPFORGE_VERIFY_SOURCE_DIR',raising=False)
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','test-only-not-a-real-token')
    monkeypatch.setenv('TELEGRAM_OWNER_ID','123')
    deploy.write_json(deploy.report_path('backend'),deploy.verify_manifest(project))
    monkeypatch.setattr(deploy,'backend_contract',lambda *a:{'director_policy':4})
    monkeypatch.setattr(deploy,'get_json',lambda *a:{'schema':1,'build_id':'abc','ui_verified':False})
    with pytest.raises(RuntimeError,match='Frontend release'):
        deploy.prepare('telegram-bot',['python','telegram_bot.py'])


def test_backend_contract_does_not_resume_disabled_cron(monkeypatch):
    payloads={'/api/health':{'status':'ok'},'/api/tiktok/config':{'duplicate_guard_version':2,'cron_draft_policy':'discard'},
      '/api/automation/viral-cc/schedule':{'cron_director_effects_policy_version':4,'cron_source_process_limit':2,'enabled':False,'scheduler_running':False},
      '/api/automation/viral-cc/long-strategy':{'version':2,'semantic_story_review_required':True,'themes':[
          {'key':key,'manual_review_required':key=='domestic_politics'} for key in
          ('mystery_story','legend_folklore','domestic_politics','food_healthy_review','food_taste_review')]}}
    monkeypatch.setattr(deploy,'get_json',lambda url:payloads[url.removeprefix('http://local')])
    assert deploy.backend_contract('http://local')['cron_enabled'] is False
    assert deploy.backend_contract('http://local')['long_strategy_version'] == 2
    payloads['/api/automation/viral-cc/long-strategy']['version']=1
    with pytest.raises(RuntimeError,match='Long strategy'):deploy.backend_contract('http://local')
    payloads['/api/automation/viral-cc/long-strategy']['version']=2
    payloads['/api/tiktok/config']['duplicate_guard_version']=1
    with pytest.raises(RuntimeError,match='guard is stale'):deploy.backend_contract('http://local')


def test_compose_command_includes_all_readiness_gates_and_shared_bot_image(tmp_path):
    compose=shutil.which('docker-compose')
    if not compose:pytest.skip('Compose CLI unavailable')
    env=tmp_path/'.env';env.write_text('FRONTEND_PORT=3033\n')
    child_env={**os.environ,'TIKTOK_AUTOMATIC_RETRY_ENABLED':'true'}
    result=subprocess.run([compose,'--env-file',str(env),'config','--format','json'],cwd=ROOT,env=child_env,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    services=json.loads(result.stdout)['services']
    backend,frontend,bot=(services[name] for name in ('backend','frontend','telegram-bot'))
    assert bot['image']==backend['image'] and 'build' not in bot
    assert frontend['depends_on']['backend']['condition']=='service_healthy'
    assert bot['depends_on']['backend']['condition']=='service_healthy'
    assert bot['depends_on']['frontend']['condition']=='service_healthy'
    assert bot['post_start'][0]['command'][-1]=='wait-ready'
    assert 'deployment_runtime.py' in backend['healthcheck']['test'][2]
    assert 'deployment-health.cjs' in frontend['healthcheck']['test'][2]
    assert backend['environment']['TIKTOK_AUTOMATIC_RETRY_ENABLED']=='true'
    assert bot['environment']['FRONTEND_BASE']=='http://127.0.0.1:3033'
    assert all(row.get('read_only') for service in (backend,frontend,bot) for row in service['volumes'] if str(row['target']).startswith('/opt/clipforge-source/'))


def test_frontend_verifies_actual_served_assets_and_rejects_mixed_builds(tmp_path):
    if not shutil.which('node'):pytest.skip('Node unavailable')
    root=tmp_path/'frontend';(root/'scripts').mkdir(parents=True)
    shutil.copy2(ROOT/'frontend/scripts/deployment-health.cjs',root/'scripts/deployment-health.cjs')
    script=r'''
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
for(const name of ['package.json','package-lock.json','next.config.ts','tsconfig.json','docker-entrypoint.sh','Dockerfile'])fs.writeFileSync(name,'{}');
for(const dir of ['app','public','.next/static'])fs.mkdirSync(dir,{recursive:true});
fs.writeFileSync('app/page.tsx','original source');
fs.writeFileSync('.next/BUILD_ID','build-a');
const js='jobDirectorRecovery history-four-columns jobPlatformQueue /reconcile dijadwalkan ulang otomatis pengaturan privasi tertunda Hasil posting perlu diperiksa';
const css='.outputWorkspacePane .jobList{grid-template-columns:repeat(4,minmax(0,1fr))}';
fs.writeFileSync('.next/static/app.js',js);fs.writeFileSync('.next/static/app.css',css);
const deploy=require('./scripts/deployment-health.cjs');
deploy.build();deploy.prepare();
process.env.CLIPFORGE_VERIFY_SOURCE_DIR=process.cwd();deploy.prepare();
fs.writeFileSync('app/page.tsx','edited while building');
assert.throws(()=>deploy.prepare(),/source changed during build/);
fs.writeFileSync('app/page.tsx','original source');
fs.writeFileSync('.next/static/app.js','bad chunk');
assert.throws(()=>deploy.prepare(),/asset mismatch/);
fs.writeFileSync('.next/static/app.js',js);
const responses={'/':'<script src="/_next/static/app.js"></script><link href="/_next/static/app.css"/>',
 '/deployment.json':fs.readFileSync('public/deployment.json','utf8'),
 '/_next/static/app.js':js,'/_next/static/app.css':css};
global.fetch=async url=>({ok:true,text:async()=>responses[new URL(url).pathname]});
(async()=>{
 await deploy.health();
 responses['/_next/static/app.js']='wrong served chunk';
 await assert.rejects(()=>deploy.health(),/Served assets differ/);
 responses['/_next/static/app.js']=js;
 responses['/deployment.json']='{"build_id":"old"}';
 await assert.rejects(()=>deploy.health(),/release mismatch/);
})().catch(error=>{console.error(error);process.exitCode=1});
'''
    result=subprocess.run(['node','-e',script],cwd=root,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


def test_detached_start_waits_until_bot_preparation_and_exec_finish(monkeypatch,capsys):
    monkeypatch.setattr('sys.argv',['deployment_runtime.py','wait-ready'])
    monkeypatch.setenv('CLIPFORGE_SERVICE','telegram-bot')
    calls=[]
    def health(role):
        calls.append(role)
        if len(calls)<3:raise RuntimeError('entrypoint still preparing')
        return {'healthy':True,'role':role}
    monkeypatch.setattr(deploy,'health',health)
    monkeypatch.setattr(deploy.time,'sleep',lambda *a:None)
    deploy.main()
    assert calls==['telegram-bot']*3
    assert json.loads(capsys.readouterr().out)['healthy'] is True


def test_detached_start_timeout_never_reports_success(monkeypatch):
    monkeypatch.setattr('sys.argv',['deployment_runtime.py','wait-ready'])
    clock=iter([0,61])
    monkeypatch.setattr(deploy.time,'monotonic',lambda:next(clock))
    def fail(role):raise RuntimeError('bot failed to start')
    monkeypatch.setattr(deploy,'health',fail)
    with pytest.raises(RuntimeError,match='bot failed to start'):deploy.main()
