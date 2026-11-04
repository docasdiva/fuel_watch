from datetime import date

import pytest

from fuelwatch import download

DAY = date(2026, 11, 3)


class FakeResponse:
    """Imite la réponse de requests.get."""

    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


def fake_get(content: bytes, calls: list):
    """Fabrique un faux requests.get qui renvoie `content` et note chaque appel."""
    def _get(url, timeout):
        calls.append(url)
        return FakeResponse(content)
    return _get


def test_download_writes_zip(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(download.requests, "get", fake_get(b"PK fake zip", calls))

    path = download.download_daily(DAY, raw_dir=tmp_path)

    assert path == tmp_path / "quotidien" / "2026-11-03.zip"
    assert path.read_bytes() == b"PK fake zip"
    assert calls == ["https://donnees.roulez-eco.fr/opendata/jour/20261103"]


def test_second_call_does_not_redownload(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(download.requests, "get", fake_get(b"PK fake zip", calls))

    download.download_daily(DAY, raw_dir=tmp_path)
    download.download_daily(DAY, raw_dir=tmp_path)

    assert len(calls) == 1


def test_force_redownloads(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(download.requests, "get", fake_get(b"PK fake zip", calls))

    download.download_daily(DAY, raw_dir=tmp_path)
    download.download_daily(DAY, raw_dir=tmp_path, force=True)

    assert len(calls) == 2


def test_html_response_raises(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(download.requests, "get", fake_get(b"<!DOCTYPE html>...", calls))

    with pytest.raises(download.SourceError):
        download.download_daily(DAY, raw_dir=tmp_path)

    assert not download.daily_path(DAY, tmp_path).exists()
