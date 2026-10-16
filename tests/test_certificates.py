"""The Mac app said "geen verbinding met kerkdienstgemist" while the site was up: its
OpenSSL looked for trusted authorities on the computer it was built on."""

import ssl
import urllib.error

import pytest

from backend import certificates, kerkdienstgemist, places


@pytest.fixture
def clean(monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    monkeypatch.setattr(certificates.sys, "platform", "darwin")


def test_the_mac_app_always_uses_the_list_it_brings(clean, monkeypatch):
    monkeypatch.setattr(places, "FROZEN", True)
    monkeypatch.setattr(certificates, "found_its_own", lambda: True)
    where = certificates.make_sure()
    assert where and certificates.os.environ["SSL_CERT_FILE"] == where


def test_a_python_without_a_list_gets_one(clean, monkeypatch):
    monkeypatch.setattr(places, "FROZEN", False)
    monkeypatch.setattr(certificates, "found_its_own", lambda: False)
    assert certificates.make_sure()


def test_a_python_with_its_own_list_keeps_it(clean, monkeypatch):
    monkeypatch.setattr(places, "FROZEN", False)
    monkeypatch.setattr(certificates, "found_its_own", lambda: True)
    assert certificates.make_sure() is None
    assert "SSL_CERT_FILE" not in certificates.os.environ


def test_a_choice_somebody_made_is_left_alone(clean, monkeypatch):
    """A church network that inspects traffic needs its own authority, set on purpose."""
    monkeypatch.setattr(places, "FROZEN", True)
    monkeypatch.setenv("SSL_CERT_FILE", "/ergens/eigen.pem")
    assert certificates.make_sure() is None
    assert certificates.os.environ["SSL_CERT_FILE"] == "/ergens/eigen.pem"


def test_windows_keeps_its_own_store(clean, monkeypatch):
    monkeypatch.setattr(certificates.sys, "platform", "win32")
    monkeypatch.setattr(places, "FROZEN", True)
    assert certificates.make_sure() is None


def test_with_the_list_there_is_something_to_trust(clean, monkeypatch):
    monkeypatch.setattr(places, "FROZEN", True)
    certificates.make_sure()
    assert certificates.trusted() > 50


def test_a_certificate_failure_is_not_called_a_dead_internet():
    failed = urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed"))
    said = kerkdienstgemist.unreachable("kerkdienstgemist.nl", failed)
    assert "beveiligingscertificaat" in said and "internet" not in said


def test_no_connection_is_still_no_connection():
    said = kerkdienstgemist.unreachable("kerkdienstgemist.nl", urllib.error.URLError(OSError("down")))
    assert "Kijk of je internet het doet" in said


def test_the_station_reports_the_certificate(monkeypatch):
    def fail(*_a, **_k):
        raise urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed"))

    monkeypatch.setattr(kerkdienstgemist, "ask", fail)
    with pytest.raises(kerkdienstgemist.NotFound, match="beveiligingscertificaat"):
        kerkdienstgemist.station("1341")
