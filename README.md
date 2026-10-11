# Compiler Differential Testing Tool

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![C++14](https://img.shields.io/badge/C%2B%2B-14-orange.svg)](https://isocpp.org/)

An automated differential testing harness for detecting semantic and behavioral divergence across compiler optimization levels (`-O0` vs `-O2`).

---

## Overview

In optimizing compilers, transformations (e.g., constant folding, dead-code elimination, vectorization, value-range propagation) must preserve the semantics of conforming source code.

This tool implements **Differential Testing** to address the test oracle problem:
1. Compiles a target C++ source file under an unoptimized baseline (`-O0`) and an optimized candidate (`-O2`).
2. Executes both binaries in isolated subprocesses using identical test input vectors.
3. Compares standard output, standard error, execution latency, and exit statuses.
4. Generates unified diffs on output divergence and flags crashes, timeouts, and anomalous exit codes.

```
                  +---------------------------+
                  |   C++ Source File (.cpp)  |
                  +-------------+-------------+
                                |
               +----------------+----------------+
               |                                 |
         gcc -O0 (Baseline)               gcc -O2 (Optimized)
               |                                 |
        [ prog_O0.exe ]                   [ prog_O2.exe ]
               |                                 |
               +----------------+----------------+
                                |
                  +-------------v-------------+
                  | Inject Identical Stdin    |
                  | Monitor Timeouts/Crashes  |
                  +-------------+-------------+
                                |
                  +-------------v-------------+
                  | Diff Output & Exit Codes  |
                  | PASS / MISMATCH / CRASH   |
                  +---------------------------+
```

---

## Features

- **Zero External Dependencies:** Built entirely with the Python 3 standard library (`subprocess`, `dataclasses`, `pathlib`, `difflib`, `unittest`).
- **Subprocess Isolation:** Compiles and executes in isolated temporary directories with automatic cleanup.
- **Fault Detection:** Identifies execution timeouts, abnormal terminations, Windows NTSTATUS exceptions (`0xC0000005`), and Unix signals (`SIGSEGV`, `SIGABRT`).
- **Telemetry & Unified Diffs:** Reports per-test execution latency and provides unified diffs on output divergence.
- **Graceful Error Handling:** Intercepts missing compiler binaries and syntax errors with captured compiler diagnostics.

---

## Repository Structure

```text
compiler-diff-tester/
├── src/
│   ├── __init__.py           # Package exports
│   ├── compiler.py           # Subprocess compiler interface with flag control
│   ├── runner.py             # Binary runner with crash and timeout telemetry
│   └── diff_engine.py        # Differential orchestrator and comparison logic
├── tests/
│   ├── __init__.py
│   └── test_diff_engine.py   # Automated unit test suite
├── examples/
│   ├── bit_ops.cpp           # Conforming C++ sample (boundary values, bit ops)
│   ├── ub_mismatch.cpp       # Deliberate UB sample (signed integer overflow)
│   ├── broken_syntax.cpp     # Compilation failure sample
│   └── inputs.txt            # Boundary and bitwise test vectors
├── diff_test.py              # CLI entry point
├── .gitignore                # Build and bytecode ignore rules
└── README.md                 # Project documentation
```

---

## Getting Started

### Prerequisites
- Python 3.8+
- GCC / G++ (or Clang) accessible in system `PATH`

```bash
g++ --version
python --version
```

### Usage

#### 1. Conforming Verification Run
Run the differential harness against a standard-compliant bitwise program:
```bash
python diff_test.py examples/bit_ops.cpp --inputs examples/inputs.txt
```

#### 2. Induced Behavioral Divergence (Undefined Behavior Demonstration)
Demonstrate optimization divergence using a signed overflow scenario:
```bash
python diff_test.py examples/ub_mismatch.cpp --inputs examples/inputs.txt
```

#### 3. CLI Flags
```bash
python diff_test.py <source.cpp> [OPTIONS]

Options:
  -i, --inputs PATH      Path to custom inputs file (supports # TEST: blocks)
  -c, --compiler PATH    Path or binary name of C++ compiler (default: g++)
  -t, --timeout FLOAT    Per-test execution timeout in seconds (default: 2.0)
  -v, --verbose          Display verbose telemetry and raw stdout
```

#### 4. Running Unit Tests
```bash
python -m unittest discover tests
```

---

## Verification Analysis: Optimization Divergence vs. Compiler Defects

A behavioral mismatch between `-O0` and `-O2` does not inherently indicate a compiler defect.

In ISO C++, the compiler's code-generation contract follows the **as-if rule**: observable behavior must be preserved only for conforming programs executing without **Undefined Behavior (UB)**.

### Example Case Study (`ub_mismatch.cpp`)
```cpp
bool check_signed_overflow_assumption(int x) {
    return (x + 1) > x;
}
```
For `x = INT_MAX` (2147483647):
- **`-O0` (Baseline):** Emits straightforward instructions. On standard two's complement architectures, `INT_MAX + 1` wraps to `INT_MIN` (-2147483648), producing `false` (`NO`).
- **`-O2` (Optimized):** The optimizer assumes conforming code never invokes signed integer overflow. Under this invariant, `x + 1 > x` is simplified to constant `true` (`YES`) at compile time.

```text
------------------------------------------------------------------------------
ID   TEST CASE                  -O0 TIME   -O2 TIME   VERDICT   
------------------------------------------------------------------------------
6    int_max_boundary           13.2ms     12.8ms     MISMATCH  
  |-- Discrepancy Detail:
  |   --- -O0 (baseline)
  |   +++ -O2 (optimized)
  |   @@ -1,3 +1,3 @@
  |   -Result of (val + 1 > val): NO
  |   +Result of (val + 1 > val): YES
------------------------------------------------------------------------------
```

### Triage Workflow
When a mismatch is detected:
1. **Sanitizer Check:** Recompile with `-fsanitize=undefined,address` to rule out source-level UB.
2. **IR Inspection:** Dump compiler intermediate representations (`-fdump-tree-all` in GCC, `-print-after-all` in Clang) to inspect pass transformations.
3. **Pass Bisection:** Disable optimization passes selectively (e.g., `-fno-tree-vrp`, `-fno-strict-aliasing`) to isolate the diverging transformation pass.

