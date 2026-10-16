"""The readiness panel: what it checks must not trip over itself."""


def test_two_checks_at_once_do_not_take_each_other_s_test_file(tmp_path, monkeypatch):
    """The panel and a report asked together, and "Mappen" went red on a healthy folder."""
    import threading

    from backend import health

    for name in ("PROJECTS_DIR", "SERVICES_DIR", "OWN_TEMPLATES"):
        monkeypatch.setattr(health, name, tmp_path / name)
    results = []
    threads = [threading.Thread(target=lambda: results.append(health._folders().ok)) for _ in range(40)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert all(results) and len(results) == 40
