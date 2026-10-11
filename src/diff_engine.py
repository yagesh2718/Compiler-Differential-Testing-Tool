"""
diff_engine.py - Differential execution engine for -O0 vs -O2 verification.
"""

from dataclasses import dataclass, field
import difflib
from enum import Enum
from pathlib import Path
import tempfile
from typing import List, Optional, Tuple

from .compiler import CppCompiler, CompilationResult
from .runner import BinaryRunner, ExecutionResult, ExecutionStatus


class DifferentialVerdict(str, Enum):
    PASS = "PASS"
    MISMATCH = "MISMATCH"
    CRASH = "CRASH"
    TIMEOUT = "TIMEOUT"
    NON_ZERO_EXIT = "NON_ZERO_EXIT"
    COMPILE_FAIL = "COMPILE_FAIL"


@dataclass
class TestCaseResult:
    test_id: int
    test_name: str
    input_data: str
    verdict: DifferentialVerdict
    result_o0: Optional[ExecutionResult] = None
    result_o2: Optional[ExecutionResult] = None
    diff_details: str = ""


@dataclass
class DifferentialReport:
    source_file: Path
    compilation_o0: Optional[CompilationResult] = None
    compilation_o2: Optional[CompilationResult] = None
    test_cases: List[TestCaseResult] = field(default_factory=list)
    has_compilation_failure: bool = False

    @property
    def total_tests(self) -> int:
        return len(self.test_cases)

    @property
    def matches(self) -> int:
        return sum(1 for t in self.test_cases if t.verdict == DifferentialVerdict.PASS)

    @property
    def mismatches(self) -> int:
        return sum(1 for t in self.test_cases if t.verdict == DifferentialVerdict.MISMATCH)

    @property
    def crashes(self) -> int:
        return sum(1 for t in self.test_cases if t.verdict == DifferentialVerdict.CRASH)

    @property
    def timeouts(self) -> int:
        return sum(1 for t in self.test_cases if t.verdict == DifferentialVerdict.TIMEOUT)

    @property
    def non_zero_exits(self) -> int:
        return sum(1 for t in self.test_cases if t.verdict == DifferentialVerdict.NON_ZERO_EXIT)


class DifferentialTester:
    def __init__(self, compiler: Optional[CppCompiler] = None, runner: Optional[BinaryRunner] = None):
        self.compiler = compiler or CppCompiler()
        self.runner = runner or BinaryRunner()

    def test_file(
        self,
        source_file: Path,
        test_inputs: List[Tuple[str, str]],
        execution_timeout_seconds: float = 2.0,
    ) -> DifferentialReport:
        source_file = source_file.resolve()
        report = DifferentialReport(source_file=source_file)

        with tempfile.TemporaryDirectory(prefix="diff_test_") as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            binary_o0 = tmp_dir / ("prog_O0.exe" if Path().suffix == ".exe" or "\\" in str(tmp_dir) else "prog_O0")
            binary_o2 = tmp_dir / ("prog_O2.exe" if Path().suffix == ".exe" or "\\" in str(tmp_dir) else "prog_O2")

            comp_o0 = self.compiler.compile(
                source_file=source_file,
                opt_level="-O0",
                output_binary=binary_o0,
            )
            report.compilation_o0 = comp_o0

            comp_o2 = self.compiler.compile(
                source_file=source_file,
                opt_level="-O2",
                output_binary=binary_o2,
            )
            report.compilation_o2 = comp_o2

            if not comp_o0.success or not comp_o2.success:
                report.has_compilation_failure = True
                return report

            for idx, (name, stdin_data) in enumerate(test_inputs, start=1):
                res_o0 = self.runner.execute(
                    binary_path=binary_o0,
                    stdin_input=stdin_data,
                    timeout_seconds=execution_timeout_seconds,
                )
                res_o2 = self.runner.execute(
                    binary_path=binary_o2,
                    stdin_input=stdin_data,
                    timeout_seconds=execution_timeout_seconds,
                )

                verdict, diff_text = self._compare_executions(res_o0, res_o2)

                report.test_cases.append(
                    TestCaseResult(
                        test_id=idx,
                        test_name=name,
                        input_data=stdin_data,
                        verdict=verdict,
                        result_o0=res_o0,
                        result_o2=res_o2,
                        diff_details=diff_text,
                    )
                )

        return report

    def _compare_executions(
        self,
        res_o0: ExecutionResult,
        res_o2: ExecutionResult,
    ) -> Tuple[DifferentialVerdict, str]:
        if res_o0.timed_out or res_o2.timed_out:
            notes = []
            if res_o0.timed_out:
                notes.append("-O0 timed out")
            if res_o2.timed_out:
                notes.append("-O2 timed out")
            return DifferentialVerdict.TIMEOUT, "; ".join(notes)

        if res_o0.status == ExecutionStatus.CRASH or res_o2.status == ExecutionStatus.CRASH:
            notes = []
            if res_o0.status == ExecutionStatus.CRASH:
                notes.append(f"-O0 crashed (code {res_o0.returncode})")
            if res_o2.status == ExecutionStatus.CRASH:
                notes.append(f"-O2 crashed (code {res_o2.returncode})")
            return DifferentialVerdict.CRASH, "; ".join(notes)

        if res_o0.returncode != res_o2.returncode:
            diff_msg = (
                f"Exit code mismatch: -O0 exited with {res_o0.returncode}, "
                f"-O2 exited with {res_o2.returncode}."
            )
            return DifferentialVerdict.MISMATCH, diff_msg

        if res_o0.returncode != 0:
            if res_o0.stdout != res_o2.stdout:
                return DifferentialVerdict.MISMATCH, "Stdout mismatch during non-zero exit."
            return DifferentialVerdict.NON_ZERO_EXIT, f"Both returned exit code {res_o0.returncode}."

        if res_o0.stdout == res_o2.stdout:
            return DifferentialVerdict.PASS, "Outputs match identically."

        diff_lines = list(
            difflib.unified_diff(
                res_o0.stdout.splitlines(keepends=True),
                res_o2.stdout.splitlines(keepends=True),
                fromfile="-O0 (baseline)",
                tofile="-O2 (optimized)",
                n=3,
            )
        )
        diff_text = "".join(diff_lines) if diff_lines else "Output strings differed."
        return DifferentialVerdict.MISMATCH, diff_text
