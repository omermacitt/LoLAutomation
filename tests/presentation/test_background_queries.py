"""Reads never block Qt or overlap; late results are ignored after close."""

import threading

from rune_pilot.presentation.controllers.background_query import BackgroundQuery


def test_query_runs_off_ui_thread_and_does_not_overlap(qt_app, wait_until):
    query = BackgroundQuery()
    gate = threading.Event()
    started = threading.Event()
    threads, results = [], []
    query.succeeded.connect(results.append)
    def read():
        threads.append(threading.get_ident())
        started.set()
        gate.wait(3)
        return "result"
    try:
        assert query.run(read)
        wait_until(started.is_set)
        assert not query.run(read)
        assert not results
        assert threads != [threading.get_ident()]
        gate.set()
        wait_until(lambda: not query.busy)
        assert results == ["result"]
    finally:
        gate.set()
        query.shutdown()


def test_closed_query_cannot_deliver_late_results(qt_app, wait_until):
    query = BackgroundQuery()
    gate, finished = threading.Event(), threading.Event()
    results = []
    query.succeeded.connect(results.append)
    def read():
        gate.wait(3)
        finished.set()
        return "too late"
    query.run(read)
    query.shutdown()
    gate.set()
    wait_until(finished.is_set)
    assert not results
    assert not query.run(lambda: "again")
