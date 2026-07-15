"""
Unit tests for scheduled/run_batch.py's control flow: everything that touches
a real browser or network is monkeypatched out, so these only verify the
orchestration logic (continues past a failing URL, writes results correctly).
"""

import json

import scheduled.run_batch as run_batch


class _FakeBrowser:
    def close(self):
        pass


class _FakeChromium:
    def launch(self, **kwargs):
        return _FakeBrowser()


class _FakePlaywright:
    def __enter__(self):
        self.chromium = _FakeChromium()
        return self

    def __exit__(self, *exc):
        return False


def _patch_common(monkeypatch, process_booking_search_side_effect):
    monkeypatch.setattr(run_batch, "sync_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(run_batch, "add_random_delay", lambda *a, **kw: None)
    monkeypatch.setattr(
        run_batch,
        "generate_search_urls",
        lambda: ["https://example.com/a", "https://example.com/b", "https://example.com/c"],
    )
    monkeypatch.setattr(run_batch, "process_booking_search", process_booking_search_side_effect)
    monkeypatch.setattr(run_batch, "save_to_excel", lambda *a, **kw: None)


def test_one_failing_url_does_not_abort_the_others(monkeypatch):
    def fake_process(browser, url):
        if url.endswith("/b"):
            raise RuntimeError("simulated navigation failure")
        return [{"Hotel Name": "Test Hotel"}]

    _patch_common(monkeypatch, fake_process)

    results = run_batch.run_batch()

    assert len(results) == 3
    assert results[0]["success"] is True
    assert results[1]["success"] is False
    assert "simulated navigation failure" in results[1]["error"]
    assert results[2]["success"] is True


def test_empty_hotel_list_counts_as_failure_not_crash(monkeypatch):
    _patch_common(monkeypatch, lambda browser, url: [])

    results = run_batch.run_batch()

    assert all(r["success"] is False for r in results)
    assert all(r["error"] == "No hotel data collected" for r in results)


def test_main_writes_results_json_and_exits_zero_on_partial_success(monkeypatch, tmp_path):
    def fake_process(browser, url):
        if url.endswith("/b"):
            raise RuntimeError("boom")
        return [{"Hotel Name": "Test Hotel"}]

    _patch_common(monkeypatch, fake_process)

    out_path = tmp_path / "results.json"
    monkeypatch.setattr("sys.argv", ["run_batch.py", str(out_path)])

    run_batch.main()  # should not raise / sys.exit since 2 of 3 succeeded

    written = json.loads(out_path.read_text())
    assert len(written) == 3
    assert sum(1 for r in written if r["success"]) == 2


def test_main_exits_nonzero_when_everything_fails(monkeypatch, tmp_path):
    _patch_common(monkeypatch, lambda browser, url: (_ for _ in ()).throw(RuntimeError("boom")))

    out_path = tmp_path / "results.json"
    monkeypatch.setattr("sys.argv", ["run_batch.py", str(out_path)])

    try:
        run_batch.main()
        raised = False
    except SystemExit as e:
        raised = True
        assert e.code == 1

    assert raised, "main() should sys.exit(1) when every URL fails"
