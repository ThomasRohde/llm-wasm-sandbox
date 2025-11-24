# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-11-24

### Fixed
- **Critical**: WASM runtime binaries now properly included in PyPI package distribution
  - Fixed hatchling configuration to bundle `bin/python.wasm` and `bin/quickjs.wasm`
  - Users no longer need to manually download WASM binaries after `pip install`
  - Package size increased to ~12MB to include both runtimes
  - Both wheel and source distributions now contain all required binaries

### Changed
- Updated build configuration to use `force-include` for binary artifacts
- Package now works out-of-the-box after installation from PyPI

## [0.1.0] - 2025-01-XX

### Added
- Initial release of LLM WASM Sandbox
- Production-grade security sandbox for executing untrusted Python code using WebAssembly
- JavaScript runtime support via QuickJS-NG WASM
- **Bundled WASM runtimes** - No separate downloads needed! `python.wasm` and `quickjs.wasm` are now included in the PyPI package
- Type-safe API with Pydantic models (`ExecutionPolicy`, `SandboxResult`)
- Multi-layered security model:
  - WASM memory safety with bounds checking
  - WASI capability-based filesystem isolation
  - Fuel-based deterministic execution limits
  - Configurable memory caps
- Persistent session management with UUID-based session IDs
- Session file operations API (`read_session_file`, `write_session_file`, `list_session_files`)
- Automatic session pruning with configurable retention policies
- Pluggable storage adapter interface for custom backends
- Python vendoring support for pure-Python packages
- **NEW: `sandbox_utils` library** - Shell-like utilities for LLM-generated code:
  - File operations: `find()`, `tree()`, `walk()`, `copy_tree()`, `remove_tree()`
  - Text processing: `grep()`, `sed()`, `head()`, `tail()`, `wc()`, `diff()`
  - Data manipulation: `group_by()`, `filter_by()`, `map_items()`, `sort_by()`, `unique()`, `chunk()`
  - Format conversions: `csv_to_json()`, `json_to_csv()`, `xml_to_dict()`
  - Shell emulation: `ls()`, `cat()`, `touch()`, `mkdir()`, `rm()`, `cp()`, `mv()`, `echo()`
  - 30+ functions with comprehensive docstrings and examples
  - All operations enforce strict `/app` sandbox boundaries
- **NEW: Vendored pure-Python packages** for enhanced capabilities:
  - `python-dateutil` - Advanced date/time parsing
  - `tabulate` - Pretty-printing tables
  - `jinja2` + `MarkupSafe` - Template rendering (requires 5B fuel budget for first import)
  - `markdown` - Markdown to HTML conversion
  - `tomli` - TOML parsing (Python <3.11 only)
  - `six` - Python 2/3 compatibility utilities
  - `attrs` - Data modeling and validation
- Structured logging with `SandboxLogger` for observability
- Rich metrics collection (fuel consumption, memory usage, execution time)
- Comprehensive test suite with 425+ tests (55 new tests for `sandbox_utils`)
- Demo scripts showcasing all major features
- Full type hints support (PEP 561 compliant with `py.typed` marker)

### Security Features
- Capability-based I/O prevents filesystem escapes
- Fuel metering prevents infinite loops and runaway computation
- Memory limits prevent memory exhaustion attacks
- Output caps prevent log flooding
- No network access (WASI baseline without sockets)
- No subprocess spawning
- Environment variable whitelist pattern

### Documentation
- Comprehensive README with architecture overview
- **NEW: `docs/PYTHON_CAPABILITIES.md`** - Detailed reference for Python runtime capabilities:
  - Complete stdlib module categorization
  - Vendored package documentation with examples
  - Common LLM code patterns and recipes
  - Performance considerations and fuel budget guidance
  - Package compatibility matrix
  - Troubleshooting guide for common issues
- **NEW: `docs/LLM_PROMPT_TEMPLATES.md`** - Templates and best practices for effective LLM prompting:
  - Templates for file processing, data analysis, text processing
  - Multi-step workflow patterns
  - Fuel budget quick reference
- LLM integration examples and best practices
- Security model documentation
- Troubleshooting guide
- Development setup instructions

### Developer Experience
- `uv` package manager support for fast dependency resolution
- Automated WASM binary fetching scripts (Python and QuickJS)
- Type checking with mypy
- Linting and formatting with ruff
- Code coverage reporting
- Performance benchmarking tools

[0.2.0]: https://github.com/ThomasRohde/llm-wasm-sandbox/releases/tag/v0.2.0
[0.1.0]: https://github.com/ThomasRohde/llm-wasm-sandbox/releases/tag/v0.1.0
