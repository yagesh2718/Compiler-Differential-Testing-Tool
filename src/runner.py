"""
runner.py - Execution controller for compiled native binaries.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import subprocess
import time
from typing import Optional


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    CRASH = "CRASH"
    TIMEOUT = "TIMEOUT"
    NON_ZERO_EXIT = "NON_ZERO_EXIT"


@dataclass
class ExecutionResult:
    status: ExecutionStatus
    stdout: str
    stderr: str
    returncode: int
    execution_time_ms: float
    timed_out: bool = False
    error_message: Optional[str] = None


class BinaryRunner:
    def __init__(self, default_timeout_seconds: float = 3.0):
        self.default_timeout_seconds = default_timeout_seconds

    def execute(
        self,
        binary_path: Path,
        stdin_input: str = "",
        timeout_seconds: Optional[float] = None,
    ) -> ExecutionResult:
        if not binary_path.is_file():
            return ExecutionResult(
                status=ExecutionStatus.CRASH,
                stdout="",
                stderr="",
                returncode=-1,
                execution_time_ms=0.0,
                error_message=f"Executable binary not found: {binary_path}",
            )

        timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout_seconds
        start_time = time.perf_counter()

        try:
            completed_proc = subprocess.run(
                [str(binary_path)],
                input=stdin_input,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            norm_stdout = completed_proc.stdout.replace("\r\n", "\n")
            norm_stderr = completed_proc.stderr.replace("\r\n", "\n")
            ret_code = completed_proc.returncode

            if ret_code == 0:
                status = ExecutionStatus.SUCCESS
            elif self._is_crash_code(ret_code):
                status = ExecutionStatus.CRASH
            else:
                status = ExecutionStatus.NON_ZERO_EXIT

            return ExecutionResult(
                status=status,
                stdout=norm_stdout,
                stderr=norm_stderr,
                returncode=ret_code,
                execution_time_ms=elapsed_ms,
            )

        except subprocess.TimeoutExpired as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            captured_stdout = (exc.stdout or "").replace("\r\n", "\n") if isinstance(exc.stdout, str) else ""
            captured_stderr = (exc.stderr or "").replace("\r\n", "\n") if isinstance(exc.stderr, str) else ""

            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                stdout=captured_stdout,
                stderr=captured_stderr,
                returncode=-1,
                execution_time_ms=elapsed_ms,
                timed_out=True,
                error_message=f"Process exceeded execution timeout of {timeout:.1f}s.",
            )

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                status=ExecutionStatus.CRASH,
                stdout="",
                stderr="",
                returncode=-1,
                execution_time_ms=elapsed_ms,
                error_message=f"Execution launch error: {exc}",
            )

    @staticmethod
    def _is_crash_code(returncode: int) -> bool:
        if returncode < 0:
            return True

        windows_crashes = {
            0xC0000005,  # Access Violation
            0xC00000FD,  # Stack Overflow
            0xC000001D,  # Illegal Instruction
            0x80000003,  # Breakpoint
            3,           # CRT abort
        }

        unsigned_code = returncode & 0xFFFFFFFF
        return (unsigned_code in windows_crashes) or (returncode in windows_crashes)
