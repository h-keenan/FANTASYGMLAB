from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "web-next/public/.well-known/apple-developer-merchantid-domain-association"


def test_apple_pay_domain_association_file_is_checked_in_and_nonempty():
    body = FILE.read_text().strip()
    assert len(body) > 1000
    assert all(ch in "0123456789abcdefABCDEF" for ch in body)
