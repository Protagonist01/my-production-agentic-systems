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
        @property
        def exitcode(self):
            return popen.returncode

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
        exitcode = 0

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


@pytest.mark.parametrize("exit_after", [0.003, None])
def test_ready_sentinel_does_not_end_join_before_exit_or_original_bound(monkeypatch, exit_after):
    # Deterministically model EOF during child shutdown, before waitpid
    # returns the status. No OS scheduler luck, worker timeout increase or retry.
    clock = [0.0]
    pauses, waits, polls = [], [], []

    def sleep(duration):
        pauses.append(duration)
        clock[0] += duration

    def wait(handles, timeout):
        waits.append(timeout)
        return handles  # EOF is already readable on every iteration.

    class Closing:
        sentinel = "invented-closing-pipe"
        exitcode = None

        def join(self, timeout):
            assert timeout == 0
            polls.append(clock[0])
            if exit_after is not None and clock[0] >= exit_after:
                self.exitcode = 0

    monkeypatch.setattr(process_control.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(process_control.time, "sleep", sleep)
    monkeypatch.setattr(process_control, "wait", wait)
    child = Closing()
    process_control.OwnedProcess(child).join(0.005)
    assert pauses and all(0 < duration <= 0.001 for duration in pauses)
    assert all(0 < timeout <= 0.005 for timeout in waits)
    assert 0.003 <= clock[0] <= 0.005
    assert child.exitcode == (None if exit_after is None else 0)
    assert len(polls) > 1


def test_zero_join_is_a_single_nonblocking_poll(monkeypatch):
    calls = []

    class Running:
        exitcode = None

        def join(self, timeout):
            calls.append(timeout)

    monkeypatch.setattr(process_control, "wait", lambda *args, **kwargs: pytest.fail("wait"))
    monkeypatch.setattr(process_control.time, "sleep", lambda _: pytest.fail("sleep"))
    process_control.OwnedProcess(Running()).join(0)
    assert calls == [0]
