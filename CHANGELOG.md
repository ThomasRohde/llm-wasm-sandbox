# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-01-XX

### Added
- Initial release of LLM WASM Sandbox
- Production-grade security sandbox for executing untrusted Python code using WebAssembly
- JavaScript runtime support via QuickJS-NG WASM
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
- Structured logging with `SandboxLogger` for observability
- Rich metrics collection (fuel consumption, memory usage, execution time)
- Comprehensive test suite with 370+ tests
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

[0.1.0]: https://github.com/ThomasRohde/llm-wasm-sandbox/releases/tag/v0.1.0
