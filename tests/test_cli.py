import base64
from datetime import date
from googlefake import page, itin, seg
from flightwatch import cli
from flightwatch.crypto import new_key

OUT = itin("TK", [seg("SOF", "IST", [2027, 1, 24], [9, 30], [2027, 1, 24], [12], 90, "TK", "1"),
                  seg("IST", "NRT", [2027, 1, 24], [15, 25], [2027, 1, 25], [8, 40], 675, "TK", "50")], 970, [205], 4400)
RET = itin("TK", [seg("NRT", "IST", [2027, 2, 8], [10], [2027, 2, 8], [17], 780, "TK", "51"),
                  seg("IST", "SOF", [2027, 2, 8], [20], [2027, 2, 8], [21, 30], 90, "TK", "2")], 1050, [180], 4400)


def transport(params):
    # Stage-2 queries carry selected segments, which name IST; stage-1 queries only name SOF and TYO
    return 200, page([RET]) if b"IST" in base64.b64decode(params["tfs"]) else page([OUT])


def test_local_pipeline_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("FLIGHTWATCH_KEY", new_key())
    monkeypatch.setattr(cli, "make_transport", lambda: transport)
    monkeypatch.setattr(cli, "today", lambda: date(2027, 1, 10))
    report = tmp_path / "report.html"
    cli.main(["local", "--limit-days", "1", "--no-email", "--no-hubs", "--interval", "0",
              "--history", str(tmp_path / "h.bin"), "--out", str(report)])
    html = report.read_text()
    assert "TK50" in html and "100%" in html
    assert (tmp_path / "h.bin").exists()


def test_incomplete_run_exits_nonzero_after_writing_report(tmp_path, monkeypatch):
    from googlefake import CONSENT
    import pytest
    monkeypatch.setenv("FLIGHTWATCH_KEY", new_key())
    monkeypatch.setattr(cli, "make_transport", lambda: (lambda p: (200, CONSENT)))
    monkeypatch.setattr(cli, "today", lambda: date(2027, 1, 10))
    report = tmp_path / "report.html"
    with pytest.raises(SystemExit) as e:
        cli.main(["local", "--limit-days", "1", "--no-email", "--no-hubs", "--interval", "0",
                  "--history", str(tmp_path / "h.bin"), "--out", str(report)])
    assert e.value.code == 1 and "INCOMPLETE" in report.read_text()


def test_fallback_check_network_error_is_unknown(monkeypatch):
    import pytest
    def boom(*a, **k):
        raise OSError("offline")
    monkeypatch.setattr(cli.urllib.request, "urlopen", boom)
    with pytest.raises(SystemExit) as e:
        cli.main(["fallback-check", "--repo", "x/y"])
    assert e.value.code == 2


def test_report_writes_github_issue_files(tmp_path, monkeypatch):
    monkeypatch.setenv("FLIGHTWATCH_KEY", new_key())
    monkeypatch.setattr(cli, "make_transport", lambda: transport)
    monkeypatch.setattr(cli, "today", lambda: date(2027, 1, 10))
    cli.main(["local", "--limit-days", "1", "--no-email", "--no-hubs", "--interval", "0",
              "--history", str(tmp_path / "h.bin"), "--out", str(tmp_path / "r.html"),
              "--issue", str(tmp_path / "issue")])
    assert "deal" in (tmp_path / "issue.title").read_text()
    assert "TK50" in (tmp_path / "issue.md").read_text()
