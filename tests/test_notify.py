import pytest
from flightwatch.notify import send_email


def test_missing_email_settings_fail_loudly(monkeypatch):
    for k in ("GMAIL_USER", "GMAIL_APP_PASSWORD", "MAIL_TO"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError):
        send_email("s", "t", "<p>h</p>", "<html></html>")
