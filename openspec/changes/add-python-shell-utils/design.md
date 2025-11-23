# Design: Python Shell-Like Utilities Library

## Context

LLM-generated code execution in WASM environments faces unique challenges:
- **Limited runtime options**: Bash/shell WASM runtimes are immature and unreliable for production use
- **Verbosity barrier**: Expressing shell-like operations using pure Python stdlib requires multiple imports and verbose code
- **LLM friction**: LLMs trained on shell commands struggle to generate equivalent Python stdlib code
- **Security constraints**: All operations must respect WASI capability-based filesystem isolation (`/app` sandbox)

The solution is a purpose-built utilities library that bridges shell idioms and Python stdlib, providing simple, LLM-friendly APIs while maintaining security boundaries.

## Goals

1. **Simplify LLM code generation**: Provide shell-like APIs that LLMs can discover and use naturally
2. **Maintain security**: All operations enforce `/app` sandbox boundaries with no path traversal
3. **Optimize for common patterns**: Cover 80% of file, text, and data operations with 20% of APIs
4. **Pure-Python only**: Work in WASM environment without native extensions
5. **Performance awareness**: All operations should complete within default fuel budget (2B instructions)

## Non-Goals

1. **Shell language parser**: Not building a DSL or shell script interpreter
2. **Network operations**: WASI baseline doesn't support networking (future extension possible)
3. **Process management**: No subprocess spawning or process control
4. **Async operations**: Current wasmtime-py doesn't expose async WASI bindings

## Architectural Decisions

### Decision 1: Modular Library Structure

**Choice**: Split utilities into focused modules (`files.py`, `text.py`, `data.py`, `formats.py`, `shell.py`)

**Rationale**:
- **Clarity**: Each module has a clear, single responsibility
- **Discoverability**: LLMs can reason about which module to import based on task type
- **Testability**: Isolated modules are easier to test comprehensively
- **Maintenance**: Changes to one category don't affect others

**Alternatives Considered**:
1. **Monolithic `utils.py`**: Rejected - harder to navigate, poor separation of concerns
2. **Flat namespace in `__init__.py`**: Rejected - namespace pollution, unclear categorization
3. **Subpackages per category**: Rejected - over-engineering for current scope

### Decision 2: Path Validation Strategy

**Choice**: Validate all user-provided paths at function entry, normalize to absolute paths within `/app`, reject `..` traversal

**Implementation Pattern**:
```python
from pathlib import Path

def validate_app_path(path: str | Path) -> Path:
    """Validate and normalize path to be within /app sandbox."""
    p = Path(path).resolve()
    app_root = Path("/app").resolve()
    
    if not str(p).startswith(str(app_root)):
        raise ValueError(f"Path must be within /app: {path}")
    
    return p
```

**Rationale**:
- **Defense in depth**: Even if WASI permissions fail, application-level validation prevents escape
- **Clear error messages**: Users get actionable feedback without exposing host paths
- **Consistent behavior**: All utilities use same validation logic

**Alternatives Considered**:
1. **Trust WASI boundaries only**: Rejected - defense in depth principle
2. **Auto-prefix `/app`**: Rejected - surprising behavior, hides user errors
3. **Path jailing with chroot-like logic**: Rejected - complexity, Windows incompatibility

### Decision 3: Error Handling Philosophy

**Choice**: Raise exceptions for security violations, return error values for expected failures

**Implementation Pattern**:
```python
def find(pattern: str, path: str = "/app", recursive: bool = True) -> list[Path]:
    """Find files matching pattern. Raises ValueError for security violations."""
    validated_path = validate_app_path(path)  # Raises ValueError
    
    try:
        results = list(validated_path.glob(pattern if recursive else f"*/{pattern}"))
        return results
    except PermissionError:
        # Expected failure - return empty list
        return []
```

**Rationale**:
- **Security failures are exceptional**: Path escapes should never happen in correct code
- **Expected failures are values**: File not found, permission denied are normal workflow cases
- **LLM-friendly**: Exceptions for bugs, return values for business logic

**Alternatives Considered**:
1. **Result[T, Error] type**: Rejected - not idiomatic Python, adds cognitive overhead
2. **Always return errors**: Rejected - Python convention uses exceptions for exceptional cases
3. **Always raise exceptions**: Rejected - forces try/except for common cases like "file not found"

### Decision 4: Fuel Budget Strategy

**Choice**: Target <50% of default fuel budget (1B instructions) for single operations, provide guidance for complex workflows

**Benchmarking Approach**:
- Measure typical operations (find 100 files, grep 1MB text, parse 10K CSV rows)
- Document fuel costs in `docs/PYTHON_CAPABILITIES.md`
- Provide policy templates for different workload types

**Rationale**:
- **Headroom for LLM logic**: Operations leave room for user code
- **Predictable behavior**: Users can estimate if workflow fits budget
- **Failure modes**: Better to fail fast with OutOfFuel than timeout

**Alternatives Considered**:
1. **Dynamic fuel allocation**: Rejected - requires runtime policy changes, complexity
2. **Operation-specific budgets**: Rejected - users control policy, not library
3. **No guidance**: Rejected - poor user experience, trial-and-error tuning

### Decision 5: Package Vendoring Criteria

**Choice**: Curate explicit whitelist of pure-Python packages, require WASM testing before inclusion

**Vetting Process**:
1. Check package for native extensions (`pip show`, extract wheel and search for `.so`/`.pyd`)
2. Test installation with `--only-binary=:all:` flag
3. Execute simple import test in WASM sandbox
4. Measure fuel consumption for basic operations
5. Add to `RECOMMENDED_PACKAGES` list in `sandbox/vendor.py`

**Rationale**:
- **Safety**: Prevents accidental inclusion of packages with C extensions
- **Quality**: Only well-tested packages available to LLMs
- **Documentation**: Clear list of supported packages for prompt engineering

**Alternatives Considered**:
1. **Auto-install on first use**: Rejected - unpredictable, security risk
2. **Allow any pure-Python package**: Rejected - no quality control, fuel budget unknowns
3. **Build-time package scanning**: Rejected - over-engineering, manual review sufficient

## Data Model

### `sandbox_utils` Module Structure

```
sandbox_utils/
├── __init__.py          # Public API exports
│   from .files import find, tree, walk, copy_tree, remove_tree
│   from .text import grep, sed, head, tail, wc, diff
│   from .data import group_by, filter_by, map_items, sort_by, unique, chunk
│   from .formats import csv_to_json, json_to_csv, yaml_to_json, json_to_yaml, xml_to_dict
│   from .shell import ls, cat, touch, mkdir, rm, cp, mv, echo
│
├── files.py             # File operations
│   - find(pattern, path, recursive) -> list[Path]
│   - tree(path, max_depth) -> str
│   - walk(path, filter_func) -> Iterator[Path]
│   - copy_tree(src, dst) -> None
│   - remove_tree(path, pattern) -> None
│
├── text.py              # Text processing
│   - grep(pattern, files, regex) -> list[tuple[str, int, str]]
│   - sed(pattern, replacement, text) -> str
│   - head(file, lines) -> str
│   - tail(file, lines) -> str
│   - wc(file) -> dict[str, int]  # {'lines': N, 'words': N, 'chars': N}
│   - diff(file1, file2) -> str
│
├── data.py              # Data manipulation
│   - group_by(items, key_func) -> dict[Any, list[Any]]
│   - filter_by(items, predicate) -> list[Any]
│   - map_items(items, transform) -> list[Any]
│   - sort_by(items, key_func, reverse) -> list[Any]
│   - unique(items, key) -> list[Any]
│   - chunk(items, size) -> Iterator[list[Any]]
│
├── formats.py           # Format conversions
│   - csv_to_json(csv_file, output) -> str | None
│   - json_to_csv(json_file, output) -> str | None
│   - yaml_to_json(yaml_str) -> str
│   - json_to_yaml(json_str) -> str
│   - xml_to_dict(xml_str) -> dict[str, Any]
│
└── shell.py             # Shell emulation
    - ls(path, all, long) -> list[str] | list[dict]
    - cat(*files) -> str
    - touch(file) -> None
    - mkdir(path, parents) -> None
    - rm(path, recursive, force) -> None
    - cp(src, dst, recursive) -> None
    - mv(src, dst) -> None
    - echo(text, file, append) -> str | None
```

## Security Model

### Threat Model

**Threats**:
1. **Path traversal**: Malicious code tries to read/write outside `/app` using `../` sequences
2. **Symlink escape**: Malicious code creates symlinks pointing to host filesystem
3. **Resource exhaustion**: Operations consume excessive fuel or memory
4. **Information disclosure**: Error messages leak host filesystem paths or system info

**Mitigations**:
1. **Application-level path validation**: `validate_app_path()` enforces `/app` boundary
2. **WASI capabilities**: Host only preopens `/app`, symlinks outside boundary fail at WASI layer
3. **Fuel budgets**: Operations fail with OutOfFuel trap before exhausting resources
4. **Safe error messages**: Exceptions use normalized paths, never expose host-specific details

### Security Review Checklist

Before merging `sandbox_utils`:
- [ ] All functions call `validate_app_path()` for user-provided paths
- [ ] No use of `os.system()`, `subprocess`, or `eval()`/`exec()`
- [ ] No dynamic imports with user-controlled module names
- [ ] Error messages don't include full path strings (only relative to `/app`)
- [ ] Docstrings don't suggest unsafe patterns
- [ ] Test suite includes attack scenarios (path traversal, symlink escape)

## Performance Considerations

### Fuel Budget Guidelines

Estimated fuel costs (with default 2B budget):

| Operation | File Size/Count | Est. Fuel | % of Budget | Notes |
|-----------|-----------------|-----------|-------------|-------|
| `find()` | 100 files | 5M | 0.25% | Linear in file count |
| `grep()` | 1MB text | 20M | 1% | Depends on regex complexity |
| `csv_to_json()` | 10K rows | 50M | 2.5% | Depends on row size |
| `tree()` | 500 directories | 10M | 0.5% | Linear in directory count |
| `json.loads()` | 1MB | 15M | 0.75% | Stdlib parser is efficient |
| `head()` | 10 lines | 1M | 0.05% | Constant time |
| `wc()` | 1MB text | 25M | 1.25% | Linear in file size |

**Guidelines**:
- Single operations: target <2% of default budget (40M instructions)
- Complex workflows: stay under 50% budget (1B instructions) to leave headroom
- Large datasets: provide chunking APIs (`chunk()`, streaming not yet supported)

### Memory Considerations

Default memory limit: 128 MB

**Memory-intensive operations**:
- `csv_to_json()` with large files: holds CSV + JSON in memory simultaneously
- `grep()` with many files: accumulates all matches before returning
- `tree()` with deep hierarchies: recursive data structure

**Best practices documented**:
- Use generators where possible (`walk()` returns iterator)
- Provide `output=file` parameters to write directly to disk
- Document memory requirements in function docstrings

## Migration Plan

No migration required - this is a new feature with no breaking changes.

**Rollout Strategy**:
1. Merge `sandbox_utils` library (phase 1)
2. Update vendor packages (phase 2)
3. Ship documentation updates (phase 3)
4. Release demos and examples (phase 4)
5. Monitor usage metrics and fuel consumption patterns
6. Gather feedback and iterate on API design

**Rollback Plan**:
If critical issues discovered:
1. Remove `sandbox_utils` from vendor/site-packages
2. Revert vendor package additions
3. Revert documentation changes
4. Existing code continues to work (no dependencies on new features)

## Open Questions

### Q1: Should `sys.path.insert(0, '/app/site-packages')` be automatic?

**Options**:
1. **Manual (current)**: Users must add `sys.path.insert()` in their code
2. **Automatic (proposed)**: PythonSandbox injects path at execution start

**Trade-offs**:
- **Manual**: Simpler security model, explicit control, but verbose for LLMs
- **Automatic**: Better UX, less boilerplate, but increased attack surface if vendored package has vulnerability

**Recommendation**: Start with manual, gather feedback, consider automatic injection with opt-out flag in future

### Q2: Should we provide policy templates?

**Examples**: `policy-text-processing.toml`, `policy-data-analysis.toml`, `policy-file-operations.toml`

**Trade-offs**:
- **Pro**: Easier for users to pick appropriate limits, better first-run experience
- **Con**: Maintenance burden, may not match actual usage patterns, premature optimization

**Recommendation**: Defer to post-launch based on user feedback and benchmarking data

### Q3: Should format conversions be synchronous or support callbacks?

**Current design**: All conversions are synchronous (load entire file, convert, return)

**Alternative**: Streaming APIs like `csv_to_json_stream(reader, writer, chunk_size=1000)`

**Trade-offs**:
- **Synchronous**: Simpler API, easier for LLMs to use, but memory-intensive for large files
- **Streaming**: Memory-efficient, but more complex API, harder for LLMs to generate correctly

**Recommendation**: Start with synchronous, add streaming variants if benchmarking shows memory issues

## Future Enhancements

Post-launch improvements (not in initial scope):

1. **Auto-inject vendored packages**: Modify `PythonSandbox` to add `/app/site-packages` to `sys.path` automatically
2. **Async utilities**: When wasmtime-py exposes async WASI, provide async variants (`async def grep_async()`)
3. **Streaming operations**: For large files, add streaming APIs to reduce memory footprint
4. **Caching layer**: Cache file listings and search results within sessions
5. **Shell DSL**: Mini-language that compiles shell-like syntax to Python (experimental)
6. **Interactive mode**: REPL-like interface for multi-turn sessions with state persistence

## References

- WASM Sandbox Architecture: `docs/WASM_SANDBOX.md`
- Vendoring System: `sandbox/vendor.py`
- WASI Capabilities: [WASI Specification](https://github.com/WebAssembly/WASI)
- Pure-Python Package Guidelines: `AUGMENT.md` (Appendix: Pure-Python Package Verification)
