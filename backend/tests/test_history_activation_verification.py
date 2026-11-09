import importlib.util
import io
from pathlib import Path
import pytest


@pytest.mark.parametrize('css_new,js_new,expected', [(False,False,False),(True,False,False),(False,True,False),(True,True,True)])
def test_http_verifier_rejects_old_and_mixed_deployment(monkeypatch, css_new, js_new, expected):
    path = Path(__file__).resolve().parents[2] / 'scripts/verify-history-frontend.py'
    spec = importlib.util.spec_from_file_location('verify_cards', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    content = {
        '/?activation-check=history-three-columns': '<link href="/_next/static/cards.css?v=1&amp;x=2"><script src="/_next/static/app.js"></script>',
        '/_next/static/cards.css?v=1&x=2': 'historyCardSweep .jobCardPreview{}' if css_new else 'historyCardSweep .jobRow{}',
        '/_next/static/app.js': 'jobCardPreview' if js_new else 'jobRow',
    }
    monkeypatch.setattr(module.urllib.request, 'urlopen', lambda url, **kwargs: io.BytesIO(content[url.removeprefix('http://test')].encode()))
    if expected:
        result = module.check_frontend('http://test')
        assert result['js'] and result['css']
    else:
        with pytest.raises(RuntimeError, match='aset lama atau campuran'):
            module.check_frontend('http://test')
