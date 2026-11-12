"""Import-light invented callables for actual spawn/timeout/crash instrumentation tests."""

import os
import time


def worker_ok():
    return "PRIVATE_RESULT_NOT_TELEMETRY"


def worker_error():
    raise ValueError("PRIVATE_EXCEPTION_NOT_TELEMETRY")


def worker_hangs():
    time.sleep(60)


def worker_dies():
    os._exit(7)
