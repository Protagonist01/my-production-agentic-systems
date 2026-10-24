"""Reproduce cross-thread reaping, without depending on a rare OS schedule."""

import os
import threading

import pytest
from agent_harness import process_control


@pytest.mark.parametrize("guarded", [False, True])
def test_cross_thread_reaping_requires_shared_control(monkeypatch, guarded):
    # Load the actual POSIX poll implementation on Windows too; no real waitpid
    # or fork call occurs. Restore every OS stub before real spawn tests run.
    monkeypatch.setattr(os, "WNOHANG", getattr(os, "WNOHANG", 1), raising=False)
    from multiprocessing import popen_fork

    reaped, release, contender, finished = (threading.Event() for _ in range(4))
    calls, observations, failures = [], [], []
    popen = object.__new__(popen_fork.Popen)
    popen.pid, popen.returncode = 12345, None

    def waitpid(pid, flags):
        calls.append(pid)
        if len(calls) != 1:
            raise ChildProcessError("invented already-reaped child")
        return pid, 0

    def status(code):
        reaped.set()
        assert release.wait(5)
        return 0

    monkeypatch.setattr(popen_fork.os, "waitpid", waitpid)
    monkeypatch.setattr(popen_fork.os, "waitstatus_to_exitcode", status, raising=False)

    class Joining:
        def join(self, timeout):
            assert timeout == 0
            popen.poll()

    class Starting:
        def start(self):
            # BaseProcess.start's global cleanup polls existing children.
            observations.append(popen.poll())

    def owner():
        try:
            process = process_control.OwnedProcess(Joining()) if guarded else Joining()
            process.join(0)
        except BaseException as error:
            failures.append(error)

    def other():
        contender.set()
        try:
            process = process_control.OwnedProcess(Starting()) if guarded else Starting()
            process.start()
        except BaseException as error:
            failures.append(error)
        finally:
            finished.set()

    first, second = threading.Thread(target=owner), threading.Thread(target=other)
    first.start()
    try:
        assert reaped.wait(5)
        second.start()
        assert contender.wait(5)
        if guarded:
            assert not finished.wait(0.05)
        else:
            assert finished.wait(5)
            assert observations == [None]  # Reaped child incorrectly appears alive.
    finally:
        release.set()
        first.join(5)
        if second.ident is not None:
            second.join(5)
    assert not first.is_alive() and not second.is_alive() and not failures
    assert observations == ([0] if guarded else [None])
    assert calls == ([12345] if guarded else [12345, 12345])


def test_waiting_for_exit_does_not_serialize_worker_lifetimes(monkeypatch):
    waiting, release, started = (threading.Event() for _ in range(3))
    failures = []

    def wait(handles, timeout):
        waiting.set()
        assert release.wait(5)
        return handles

    class Waiting:
        sentinel = "invented-sentinel"

        def join(self, timeout):
            assert timeout == 0

    class Starting:
        def start(self):
            started.set()

    def owner():
        try:
            process_control.OwnedProcess(Waiting()).join(5)
        except BaseException as error:
            failures.append(error)

    monkeypatch.setattr(process_control, "wait", wait)
    thread = threading.Thread(target=owner)
    thread.start()
    try:
        assert waiting.wait(5)
        process_control.OwnedProcess(Starting()).start()
        assert started.is_set()
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive() and not failures
