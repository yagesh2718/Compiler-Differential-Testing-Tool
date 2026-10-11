#!/usr/bin/env python3
"""
diff_test.py - CLI tool for C++ compiler differential testing (-O0 vs -O2).
"""

import argparse
from pathlib import Path
import sys
import textwrap
from typing import List, Optional, Tuple

from src.compiler import CppCompiler, CompilerNotFoundError
from src.runner import BinaryRunner
from src.diff_engine import DifferentialTester, DifferentialVerdict, DifferentialReport


def parse_inputs_file(inputs_path: Path) -> List[Tuple[str, str]]:
    if not inputs_path.is_file():
        raise FileNotFoundError(f"Inputs file not found: {inputs_path}")

    content = inputs_path.read_text(encoding="utf-8")
    tests: List[Tuple[str, str]] = []

    if "# TEST:" in content:
        current_name: Optional[str] = None
        current_lines: List[str] = []
        for line in content.splitlines():
            if line.startswith("# TEST:"):
                if current_name is not None:
                    tests.append((current_name, "\n".join(current_lines).strip() + "\n"))
                    current_lines = []
                current_name = line.replace("# TEST:", "").strip()
            else:
                if current_name is not None and not line.startswith("#"):
                    current_lines.append(line)
        if current_name is not None and (current_lines or current_name):
            tests.append((current_name, "\n".join(current_lines).strip() + "\n"))
    else:
        for idx, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                tests.append((f"input_line_{idx}", stripped + "\n"))

    return tests


def get_default_boundary_tests() -> List[Tuple[str, str]]:
    return [
        ("zero_identity", "0 0\n"),
        ("positive_integers", "42 17\n"),
        ("negative_operands", "-15 -3\n"),
        ("mixed_signs", "-100 25\n"),
        ("int_max_boundary", "2147483647 1\n"),
        ("int_min_boundary", "-2147483648 1\n"),
        ("all_ones_mask", "-1 255\n"),
        ("power_of_two", "1024 16\n"),
        ("bitwise_shifts", "64 3\n"),
        ("alternating_bits", "1431655765 2863311530\n"),
    ]


def print_banner() -> None:
    print("=" * 78)
    print("               COMPILER DIFFERENTIAL TESTING TOOL                     ")
    print("         Automated C++ Optimization Verification (-O0 vs -O2)         ")
    print("=" * 78)


def print_report(report: DifferentialReport, verbose: bool = False) -> None:
    print(f"\n[Target Source] : {report.source_file.name}")
    print(f"[Absolute Path] : {report.source_file}")

    print("-" * 78)
    print("COMPILATION PHASE:")
    if report.compilation_o0:
        o0_status = "SUCCESS" if report.compilation_o0.success else "FAILED"
        print(f"  -O0 (Baseline)  : {o0_status} in {report.compilation_o0.compile_time_ms:.1f}ms")
        if not report.compilation_o0.success:
            print(f"      Compiler Stderr:\n{textwrap.indent(report.compilation_o0.stderr.strip(), '      ')}")
    if report.compilation_o2:
        o2_status = "SUCCESS" if report.compilation_o2.success else "FAILED"
        print(f"  -O2 (Optimized) : {o2_status} in {report.compilation_o2.compile_time_ms:.1f}ms")
        if not report.compilation_o2.success:
            print(f"      Compiler Stderr:\n{textwrap.indent(report.compilation_o2.stderr.strip(), '      ')}")

    if report.has_compilation_failure:
        print("\n[ABORT] Differential testing aborted due to compilation failure.")
        return

    print("-" * 78)
    print(f"{'ID':<4} {'TEST CASE':<26} {'-O0 TIME':<10} {'-O2 TIME':<10} {'VERDICT':<10}")
    print("-" * 78)

    for tc in report.test_cases:
        t_o0 = f"{tc.result_o0.execution_time_ms:.1f}ms" if tc.result_o0 else "N/A"
        t_o2 = f"{tc.result_o2.execution_time_ms:.1f}ms" if tc.result_o2 else "N/A"
        print(f"{tc.test_id:<4} {tc.test_name:<26} {t_o0:<10} {t_o2:<10} {tc.verdict.value:<10}")

        if tc.verdict == DifferentialVerdict.MISMATCH or (verbose and tc.verdict != DifferentialVerdict.PASS):
            print("  |-- Discrepancy Detail:")
            if tc.diff_details:
                indented_diff = textwrap.indent(tc.diff_details.strip(), "  |   ")
                print(indented_diff)
            if verbose and tc.result_o0 and tc.result_o2:
                print(f"  |   Stdout -O0: {repr(tc.result_o0.stdout)}")
                print(f"  |   Stdout -O2: {repr(tc.result_o2.stdout)}")
            print("  " + "-" * 74)

    print("=" * 78)
    print("TEST EXECUTION SUMMARY:")
    print(f"  Total Tests Executed : {report.total_tests}")
    print(f"  Matching Outputs (PASS) : {report.matches}")
    print(f"  Output Mismatches   : {report.mismatches}")
    print(f"  Program Crashes     : {report.crashes}")
    print(f"  Timeouts            : {report.timeouts}")
    print(f"  Non-zero Exits      : {report.non_zero_exits}")
    print("-" * 78)

    if report.mismatches > 0:
        print("\n[!] VERIFICATION ADVISORY - BEHAVIORAL MISMATCH DETECTED:")
        print("  1. In standard C++, an optimization-level discrepancy does not necessarily")
        print("     indicate an internal compiler bug.")
        print("  2. Discrepancies often originate from Undefined Behavior (UB) in the source code")
        print("     (e.g., signed integer overflow, strict aliasing violations, reading uninitialized memory).")
        print("  3. Recommended verification next steps: Recompile with -fsanitize=undefined,address")
        print("     to isolate application UB before filing a compiler ticket.")
    elif report.total_tests > 0 and report.matches == report.total_tests:
        print("\n[+] VERIFICATION STATUS: ALL TESTS PASSED.")
        print("  Outputs remained consistent across unoptimized (-O0) and optimized (-O2) codegen.")

    print("\n[SCOPE NOTICE]: Operates on host CPU toolchains (GCC/Clang).")
    print("=" * 78)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Differential Testing Tool for C++ Compilers (-O0 vs -O2)"
    )
    parser.add_argument("source", type=Path, help="Path to C++ source file (.cpp)")
    parser.add_argument("--inputs", "-i", type=Path, default=None, help="Path to custom test inputs file")
    parser.add_argument("--compiler", "-c", type=str, default="g++", help="C++ compiler executable (default: g++)")
    parser.add_argument("--timeout", "-t", type=float, default=2.0, help="Per-test timeout in seconds (default: 2.0)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print verbose execution telemetry and diffs")

    args = parser.parse_args()

    print_banner()

    source_path = args.source
    if not source_path.is_file():
        print(f"\n[ERROR] Source file not found: {source_path}")
        return 1

    print(f"[*] Analyzing target: {source_path.name}")

    try:
        compiler = CppCompiler(compiler_binary=args.compiler)
    except CompilerNotFoundError as err:
        print(f"\n[ERROR] {err}")
        return 1

    runner = BinaryRunner(default_timeout_seconds=args.timeout)
    tester = DifferentialTester(compiler=compiler, runner=runner)

    if args.inputs:
        try:
            test_inputs = parse_inputs_file(args.inputs)
            print(f"[*] Loaded {len(test_inputs)} test cases from {args.inputs.name}")
        except Exception as exc:
            print(f"\n[ERROR] Failed to load inputs file: {exc}")
            return 1
    else:
        test_inputs = get_default_boundary_tests()
        print(f"[*] Using built-in test suite ({len(test_inputs)} boundary/bitwise cases).")

    report = tester.test_file(
        source_file=source_path,
        test_inputs=test_inputs,
        execution_timeout_seconds=args.timeout,
    )

    print_report(report, verbose=args.verbose)

    if report.has_compilation_failure:
        return 1
    if report.mismatches > 0 or report.crashes > 0 or report.timeouts > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
