## ADDED Requirements

### Requirement: Available Python Capabilities Documentation

The project documentation SHALL comprehensively describe all Python capabilities available in the WASM sandbox, including standard library modules, vendored packages, and shell-like utilities.

#### Scenario: README capabilities section

- **WHEN** developers read the `README.md` file
- **THEN** a dedicated "Available Python Capabilities" section is present after "LLM Integration"
- **AND** the section categorizes and lists available standard library modules by function:
  - File & Path Operations (pathlib, os.path, shutil, glob, fnmatch)
  - Data Formats (json, csv, xml.etree.ElementTree, tomllib, pickle, sqlite3)
  - Text Processing (re, string, textwrap, difflib)
  - Data Structures & Algorithms (collections, itertools, functools, heapq, bisect)
  - Date & Time (datetime, time, calendar)
  - Math & Statistics (math, statistics, random, decimal, fractions)
  - Utilities (logging, argparse, configparser, base64, hashlib, secrets, uuid)
- **AND** the section lists vendored pure-Python packages with descriptions
- **AND** the section includes code examples for `sandbox_utils` shell-like operations

#### Scenario: README vendored package usage

- **WHEN** developers read the "Troubleshooting" section in `README.md`
- **THEN** an entry explains how to use vendored packages with code example:
  ```python
  import sys
  sys.path.insert(0, '/app/site-packages')
  import yaml  # Now pyyaml is available
  ```
- **AND** the entry clarifies that WASM environment doesn't auto-discover site-packages

#### Scenario: Detailed capabilities reference guide

- **WHEN** developers consult `docs/PYTHON_CAPABILITIES.md`
- **THEN** the document provides comprehensive reference including:
  - Complete stdlib module list categorized by functionality
  - Vendored package documentation links and use cases
  - Common LLM code patterns and recipes for shell-like tasks
  - Performance considerations in WASM environment
  - Fuel budget guidance for different operation types with examples

#### Scenario: LLM prompt templates

- **WHEN** developers consult `docs/LLM_PROMPT_TEMPLATES.md`
- **THEN** the document provides prompt templates for:
  - File processing tasks (with context about /app prefix, available modules, error handling)
  - Data analysis tasks (with examples of importing vendored packages)
  - Text processing tasks (with `sandbox_utils.text` examples)
  - Report generation tasks (with `tabulate` and `jinja2` examples)

### Requirement: Shell Workflow Demonstrations

The project SHALL provide comprehensive demonstrations and examples showcasing `sandbox_utils` capabilities in realistic workflows.

#### Scenario: Extended demo.py showcases

- **WHEN** developers run `demo.py`
- **THEN** the demo includes a `demo_shell_utilities()` function demonstrating:
  - Directory tree exploration using `tree()`
  - File search using `find()`
  - Text search across files using `grep()`
  - Output showing discovered files and matched lines
- **AND** the demo includes a `demo_data_processing()` function demonstrating:
  - Creating sample CSV data
  - CSV to JSON conversion using `csv_to_json()`
  - Data grouping using `group_by()`
  - Data filtering using `filter_by()`
  - Output showing transformed data structures

#### Scenario: File processing workflow examples

- **WHEN** developers explore `examples/shell_workflows/file_processing.py`
- **THEN** the example demonstrates:
  - Recursive file search and filtering with `find()` and patterns
  - Batch file renaming using `mv()` in loops
  - Directory tree generation with `tree()` for documentation

#### Scenario: Text analysis workflow examples

- **WHEN** developers explore `examples/shell_workflows/text_analysis.py`
- **THEN** the example demonstrates:
  - Log file parsing and analysis with `grep()` for error patterns
  - Text search and replace with `sed()` for bulk updates
  - Word frequency analysis combining `cat()`, `wc()`, and Python stdlib

#### Scenario: Data transformation workflow examples

- **WHEN** developers explore `examples/shell_workflows/data_transformation.py`
- **THEN** the example demonstrates:
  - CSV to JSON conversion with `csv_to_json()` for API preparation
  - Data aggregation and grouping with `group_by()` for reporting
  - Report generation using `tabulate` for pretty-printed tables

#### Scenario: Example inline documentation

- **WHEN** developers read example files in `examples/shell_workflows/`
- **THEN** each example includes inline comments explaining:
  - Purpose of each operation
  - Expected input and output
  - How the example relates to LLM code generation use cases

### Requirement: Comprehensive Testing Coverage

The `sandbox_utils` library SHALL have comprehensive test coverage validating functionality, security boundaries, and performance characteristics.

#### Scenario: Functional tests for all modules

- **WHEN** developers run `pytest tests/test_sandbox_utils.py`
- **THEN** the test suite includes tests for:
  - All functions in `files.py` module
  - All functions in `text.py` module
  - All functions in `data.py` module
  - All functions in `formats.py` module
  - All functions in `shell.py` module
- **AND** each function has multiple test cases covering normal operation and edge cases

#### Scenario: Security boundary tests

- **WHEN** developers run security tests in `tests/test_sandbox_utils.py`
- **THEN** the test suite validates:
  - Path validation rejects paths outside `/app`
  - `..` traversal sequences are blocked with ValueError
  - Error messages don't leak host filesystem paths
  - Symlink attempts outside `/app` fail safely

#### Scenario: Performance benchmark tests

- **WHEN** developers run performance tests
- **THEN** the test suite measures fuel consumption for:
  - `find()` with 10, 100, and 1000 files
  - `grep()` with 1KB, 1MB, and 10MB text files
  - `csv_to_json()` with 100, 1K, and 10K row CSV files
  - `tree()` with 10, 100, and 500 directory structures
- **AND** test results validate operations complete within documented fuel budgets

#### Scenario: Vendored package WASM tests

- **WHEN** developers run vendored package tests
- **THEN** the test suite executes simple import and usage tests for each vendored package:
  - Imports succeed using `sys.path.insert(0, '/app/site-packages')`
  - Basic operations execute successfully in WASM environment
  - No ImportError or ModuleNotFoundError exceptions occur

#### Scenario: Test coverage requirements

- **WHEN** developers run `pytest --cov=sandbox_utils`
- **THEN** the `sandbox_utils` module achieves >90% code coverage
- **AND** all critical security validation paths are covered by tests
- **AND** all public API functions have at least one test case
