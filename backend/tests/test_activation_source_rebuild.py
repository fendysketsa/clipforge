"""Exercise the Bash source/image race guard without Docker or runtime changes."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT=Path(__file__).resolve().parents[2]/'scripts/activate-youtube-quiet-check.sh'


def function(name):
    source=SCRIPT.read_text()
    body=source.split(name+'() {\n',1)[1].split('\n}\n',1)[0]
    return name+'() {\n'+body+'\n}\n'


def scenario(name):
    code='''set -uo pipefail
source_version=new
image_version=old
build_source_fingerprint=old
source_rebuilds=0
skip_build=false
builds=0
source_fingerprint() { printf '%s' "$source_version"; }
verify_image_sources() { [[ "$source_version" == "$image_version" ]]; }
python() {
  [[ "$1" == scripts/build-backend-image.py ]] || return 90
  builds=$((builds+1))
  image_version="$source_version"
  case "$SCENARIO" in
    continuous) source_version="next-$builds" ;;
    build_failure) return 17 ;;
  esac
}
docker() { printf 'image-%s' "$builds"; }
case "$SCENARIO" in
  stable_mismatch) build_source_fingerprint=new ;;
  skip_build) skip_build=true ;;
  already_matches) image_version=new ;;
esac
'''+function('ensure_image_sources')+'''
ensure_image_sources
status=$?
if [[ "$SCENARIO" == idle_edit && "$status" == 0 ]]; then
  source_version=after-idle
  ensure_image_sources
  status=$?
fi
printf 'RESULT:%s:%s:%s:%s\\n' "$status" "$builds" "$image_version" "$source_version"
'''
    return subprocess.run(['bash','-c',code],env={**os.environ,'SCENARIO':name},
        text=True,capture_output=True,timeout=10)


@pytest.mark.parametrize('name,status,builds',[
    ('source_changed',0,1),('idle_edit',0,2),('already_matches',0,0),
    ('stable_mismatch',1,0),('skip_build',1,0),('continuous',1,2),('build_failure',17,1),
])
def test_only_changed_source_is_rebuilt_and_retry_budget_is_shared(name,status,builds):
    result=scenario(name)
    assert result.returncode==0,result.stderr
    assert f'RESULT:{status}:{builds}:' in result.stdout
    if name=='stable_mismatch':assert 'Source files stayed unchanged' in result.stderr
    if name=='skip_build':assert 'rerun without --skip-build' in result.stderr
    if name=='continuous':assert 'Source changed repeatedly' in result.stderr


def test_fingerprint_tracks_bytes_even_when_mtime_is_preserved(tmp_path):
    folder=tmp_path/'backend';folder.mkdir()
    path=folder/'api.py';path.write_text('first source')
    stamp=path.stat()
    command='modules=(api)\n'+function('source_fingerprint')+'\nsource_fingerprint\n'
    # Use the tested Python interpreter without depending on a shell's venv.
    binary=tmp_path/'bin';binary.mkdir();(binary/'python').symlink_to(sys.executable)
    env={**os.environ,'PATH':str(binary)+os.pathsep+os.environ['PATH']}
    def read():
        return subprocess.check_output(['bash','-c',command],cwd=tmp_path,env=env,text=True).strip()
    first=read();path.write_text('other source');os.utime(path,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
    assert first!=read()
    path.write_text('first source')
    assert first==read()
