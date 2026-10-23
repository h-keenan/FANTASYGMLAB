from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

ROOT = Path(__file__).resolve().parents[1]
STALE = 'fantasygm' + '-lab-stripe-webhook'

def test_current_executables_do_not_guess_stale_host():
    for folder in ('modules', 'services', 'scripts'):
        for path in (ROOT / folder).glob('*.py'):
            assert STALE not in path.read_text(encoding='utf-8'), path


def test_historical_docs_labeled():
    for path in (ROOT / 'docs').glob('*.md'):
        text = path.read_text(encoding='utf-8')
        if STALE in text:
            assert 'historical' in text.lower(), path

def test_service_metadata():
    from services import stripe_webhook_service as service
    assert service.EXPECTED_PUBLIC_HOST == 'https://fantasygmlab-stripe-webhook.onrender.com'
