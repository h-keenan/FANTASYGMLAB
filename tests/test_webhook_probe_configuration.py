from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from modules import webhook_probe_config as config

ROOT = Path(__file__).resolve().parents[1]
STALE = 'fantasygm' + '-lab-stripe-webhook'

def test_current_executables_do_not_guess_stale_host():
    for folder in ('modules', 'services', 'scripts'):
        for path in (ROOT / folder).glob('*.py'):
            assert STALE not in path.read_text(encoding='utf-8'), path

def test_configured_url_and_readiness():
    urls = config.webhook_probe_urls({config.HEALTH_URL_ENV: 'https://ops.example/prefix/health'})
    assert urls['health'] == 'https://ops.example/prefix/health'
    assert urls['ready'] == 'https://ops.example/prefix/ready'
    assert urls['webhook'] == 'https://ops.example/prefix/stripe/webhook'
    assert config.webhook_probe_urls({}) == {'status': 'not_configured'}

@pytest.mark.parametrize('url', ['https://user:SECRET@example.com/health', 'https://example.com/health?token=SECRET', 'https://example.com/health#SECRET', 'http://example.com/health'])
def test_invalid_configuration_is_redacted(url):
    assert config.webhook_probe_urls({config.HEALTH_URL_ENV: url}) == {'status': 'invalid_configuration'}

def test_public_probe_missing_config_makes_no_request():
    from scripts import founder_beta_ops_public_probe as public
    with patch.object(public, 'probe_webhook') as probe:
        rows = public.webhook_results({})
    probe.assert_not_called()
    assert [row['configuration'] for row in rows] == ['not_configured'] * 2

def test_public_health_and_ready_are_separate():
    from scripts import founder_beta_ops_public_probe as public
    with patch.object(public, 'probe_webhook', side_effect=[{'ok': True, 'status': 200}, {'ok': False, 'status': 503}]) as probe:
        rows = public.webhook_results({config.HEALTH_URL_ENV: 'https://example.com/health'})
    assert [c.args[0] for c in probe.call_args_list] == ['https://example.com/health', 'https://example.com/ready']
    assert rows[0]['ok'] and not rows[1]['ok']

def test_founder_ops_honors_configuration():
    from modules import founder_ops
    with patch.object(founder_ops, '_probe_webhook_health', return_value='ok') as probe:
        snap = founder_ops.collect_ops_snapshot(environ={config.HEALTH_URL_ENV: 'https://example.com/health'}, secrets={}, session_state={})
    probe.assert_called_once_with('https://example.com/health')
    assert snap.stripe_webhook_health == 'ok'

def test_probe_does_not_echo_response_or_exception_secrets():
    from urllib.error import URLError
    response = MagicMock(status=200)
    response.read.return_value = b'SECRET'
    response.__enter__.return_value = response
    with patch.object(config, 'urlopen', return_value=response):
        assert config.probe_webhook('https://example.com/health') == {'ok': True, 'status': 200}
    with patch.object(config, 'urlopen', side_effect=URLError('SECRET')):
        assert 'SECRET' not in str(config.probe_webhook('https://example.com/health'))

def test_historical_docs_labeled():
    for path in (ROOT / 'docs').glob('*.md'):
        text = path.read_text(encoding='utf-8')
        if STALE in text:
            assert 'historical' in text.lower(), path

def test_service_metadata():
    from services import stripe_webhook_service as service
    assert service.EXPECTED_PUBLIC_HOST == 'https://fantasygmlab-stripe-webhook.onrender.com'
