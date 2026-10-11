"""
compiler.py - Subprocess-based C++ compiler interface.
"""

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import time
from typing import List, Optional


class CompilerNotFoundError(RuntimeError):
    pass


@dataclass
class CompilationResult:
    success: bool
    opt_level: str
    executable_path: Optional[Path]
    stdout: str
    stderr: str
    returncode: int
    compile_time_ms: float
    command: List[str]


class CppCompiler:
    def __init__(self, compiler_binary: str = "g++"):
        self.compiler_binary = compiler_binary
        self._verify_compiler_installed()

    def _verify_compiler_installed(self) -> None:
        if shutil.which(self.compiler_binary) is None:
            raise CompilerNotFoundError(
                f"Compiler binary '{self.compiler_binary}' was not found in PATH."
            )

    def compile(
        self,
        source_file: Path,
        opt_level: str,
        output_binary: Path,
        extra_flags: Optional[List[str]] = None,
        timeout_seconds: float = 30.0,
    ) -> CompilationResult:
        if not source_file.is_file():
            raise FileNotFoundError(f"Source file not found: {source_file}")

        flags = extra_flags or ["-std=c++14", "-Wall"]
        cmd = [self.compiler_binary, opt_level, str(source_file), "-o", str(output_binary)] + flags

        start_time = time.perf_counter()
        try:
            completed_proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            success = (completed_proc.returncode == 0) and output_binary.is_file()

            return CompilationResult(
                success=success,
                opt_level=opt_level,
                executable_path=output_binary if success else None,
                stdout=completed_proc.stdout,
                stderr=completed_proc.stderr,
                returncode=completed_proc.returncode,
                compile_time_ms=elapsed_ms,
                command=cmd,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return CompilationResult(
                success=False,
                opt_level=opt_level,
                executable_path=None,
                stdout=exc.stdout or "" if isinstance(exc.stdout, str) else "",
                stderr=f"Compilation timed out after {timeout_seconds}s.",
                returncode=-1,
                compile_time_ms=elapsed_ms,
                command=cmd,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return CompilationResult(
                success=False,
                opt_level=opt_level,
                executable_path=None,
                stdout="",
                stderr=f"Compilation error: {exc}",
                returncode=-1,
                compile_time_ms=elapsed_ms,
                command=cmd,
            )
