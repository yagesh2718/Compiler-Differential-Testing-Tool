"""
test_diff_engine.py - Unit test suite for differential engine.
"""

from pathlib import Path
import tempfile
import unittest

from src.compiler import CppCompiler, CompilerNotFoundError
from src.runner import BinaryRunner, ExecutionResult, ExecutionStatus
from src.diff_engine import DifferentialTester, DifferentialVerdict
from diff_test import parse_inputs_file


class TestCompilerDifferentialEngine(unittest.TestCase):
    def test_missing_compiler_raises_error(self):
        with self.assertRaises(CompilerNotFoundError):
            CppCompiler(compiler_binary="non_existent_compiler_binary_xyz")

    def test_output_comparison_identical_match(self):
        tester = DifferentialTester()
        res_o0 = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            stdout="Output: 0x10\n",
            stderr="",
            returncode=0,
            execution_time_ms=12.0,
        )
        res_o2 = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            stdout="Output: 0x10\n",
            stderr="",
            returncode=0,
            execution_time_ms=10.0,
        )

        verdict, diff_text = tester._compare_executions(res_o0, res_o2)
        self.assertEqual(verdict, DifferentialVerdict.PASS)
        self.assertEqual(diff_text, "Outputs match identically.")

    def test_output_comparison_mismatch_detected(self):
        tester = DifferentialTester()
        res_o0 = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            stdout="Result: NO\n",
            stderr="",
            returncode=0,
            execution_time_ms=15.0,
        )
        res_o2 = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            stdout="Result: YES\n",
            stderr="",
            returncode=0,
            execution_time_ms=14.0,
        )

        verdict, diff_text = tester._compare_executions(res_o0, res_o2)
        self.assertEqual(verdict, DifferentialVerdict.MISMATCH)
        self.assertIn("-Result: NO", diff_text)
        self.assertIn("+Result: YES", diff_text)

    def test_execution_timeout_classification(self):
        tester = DifferentialTester()
        res_o0 = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            stdout="Done\n",
            stderr="",
            returncode=0,
            execution_time_ms=25.0,
        )
        res_o2 = ExecutionResult(
            status=ExecutionStatus.TIMEOUT,
            stdout="",
            stderr="",
            returncode=-1,
            execution_time_ms=2000.0,
            timed_out=True,
        )

        verdict, notes = tester._compare_executions(res_o0, res_o2)
        self.assertEqual(verdict, DifferentialVerdict.TIMEOUT)
        self.assertIn("-O2 timed out", notes)

    def test_crash_exit_code_detection(self):
        self.assertTrue(BinaryRunner._is_crash_code(0xC0000005))
        self.assertTrue(BinaryRunner._is_crash_code(-11))

        tester = DifferentialTester()
        res_o0 = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            stdout="OK\n",
            stderr="",
            returncode=0,
            execution_time_ms=20.0,
        )
        res_o2 = ExecutionResult(
            status=ExecutionStatus.CRASH,
            stdout="",
            stderr="Segmentation Fault",
            returncode=-11,
            execution_time_ms=5.0,
        )

        verdict, notes = tester._compare_executions(res_o0, res_o2)
        self.assertEqual(verdict, DifferentialVerdict.CRASH)

    def test_inputs_parser_blocks(self):
        sample_file_content = (
            "# Header comments\n\n"
            "# TEST: case_one\n"
            "100 200\n\n"
            "# TEST: case_two\n"
            "-50 99\n"
        )
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as tmp:
            tmp.write(sample_file_content)
            tmp_path = Path(tmp.name)

        try:
            parsed = parse_inputs_file(tmp_path)
            self.assertEqual(len(parsed), 2)
            self.assertEqual(parsed[0][0], "case_one")
            self.assertEqual(parsed[0][1], "100 200\n")
            self.assertEqual(parsed[1][0], "case_two")
            self.assertEqual(parsed[1][1], "-50 99\n")
        finally:
            tmp_path.unlink()

    def test_compilation_failure_gracefully_reported(self):
        broken_cpp = "int main() { syntax error here; return 0; }"
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".cpp") as tmp:
            tmp.write(broken_cpp)
            tmp_path = Path(tmp.name)

        try:
            tester = DifferentialTester()
            report = tester.test_file(
                source_file=tmp_path,
                test_inputs=[("dummy", "0 0\n")],
            )
            self.assertTrue(report.has_compilation_failure)
            self.assertFalse(report.compilation_o0.success)
            self.assertIn("error", report.compilation_o0.stderr.lower())
        finally:
            tmp_path.unlink()


if __name__ == "__main__":
    unittest.main()
