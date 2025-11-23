## ADDED Requirements

### Requirement: Shell-Like Utilities Library

The Python runtime SHALL provide a `sandbox_utils` pure-Python library in `vendor/site-packages/` offering shell-like utilities for file operations, text processing, data manipulation, format conversions, and shell command emulation.

#### Scenario: File operations utilities

- **WHEN** LLM-generated code imports `sandbox_utils.files`
- **THEN** the following functions are available:
  - `find(pattern, path="/app", recursive=True)` - glob-style file search returning list of Path objects
  - `tree(path="/app", max_depth=None)` - directory tree visualization returning formatted string
  - `walk(path="/app", filter_func=None)` - filtered directory traversal returning iterator
  - `copy_tree(src, dst)` - recursive copy with filtering
  - `remove_tree(path, pattern=None)` - safe recursive deletion

#### Scenario: Text processing utilities

- **WHEN** LLM-generated code imports `sandbox_utils.text`
- **THEN** the following functions are available:
  - `grep(pattern, files, regex=True)` - search across files returning list of (filename, line_num, line) tuples
  - `sed(pattern, replacement, text)` - regex-based replacement returning modified string
  - `head(file, lines=10)` - read first N lines returning string
  - `tail(file, lines=10)` - read last N lines returning string
  - `wc(file)` - word/line/char count returning dict with 'lines', 'words', 'chars' keys
  - `diff(file1, file2)` - simple diff output returning formatted string

#### Scenario: Data manipulation utilities

- **WHEN** LLM-generated code imports `sandbox_utils.data`
- **THEN** the following functions are available:
  - `group_by(items, key_func)` - group items by key returning dict
  - `filter_by(items, predicate)` - functional filtering returning list
  - `map_items(items, transform)` - functional mapping returning list
  - `sort_by(items, key_func, reverse=False)` - custom sorting returning list
  - `unique(items, key=None)` - deduplication returning list
  - `chunk(items, size)` - split into chunks returning iterator

#### Scenario: Format conversion utilities

- **WHEN** LLM-generated code imports `sandbox_utils.formats`
- **THEN** the following functions are available:
  - `csv_to_json(csv_file, output=None)` - CSV to JSON conversion returning string or None if output file specified
  - `json_to_csv(json_file, output=None)` - JSON to CSV conversion returning string or None if output file specified
  - `yaml_to_json(yaml_str)` - YAML to JSON conversion returning string
  - `json_to_yaml(json_str)` - JSON to YAML conversion returning string
  - `xml_to_dict(xml_str)` - XML to dict conversion returning dictionary

#### Scenario: Shell command emulation utilities

- **WHEN** LLM-generated code imports `sandbox_utils.shell`
- **THEN** the following functions are available:
  - `ls(path="/app", all=False, long=False)` - directory listing returning list of strings or list of dicts if long=True
  - `cat(*files)` - concatenate and print files returning string
  - `touch(file)` - create empty file returning None
  - `mkdir(path, parents=True)` - create directories returning None
  - `rm(path, recursive=False, force=False)` - remove files/dirs returning None
  - `cp(src, dst, recursive=False)` - copy files/dirs returning None
  - `mv(src, dst)` - move/rename files returning None
  - `echo(text, file=None, append=False)` - print or write text returning string or None if file specified

#### Scenario: Security path validation

- **WHEN** any `sandbox_utils` function receives a file path parameter
- **THEN** the path is validated to be within `/app` sandbox boundary
- **AND** paths containing `..` traversal sequences are rejected with ValueError
- **AND** error messages do not expose host filesystem paths

#### Scenario: Public API exports

- **WHEN** LLM-generated code imports `sandbox_utils`
- **THEN** all utility functions are exported in the package-level `__init__.py`
- **AND** functions can be imported directly: `from sandbox_utils import find, grep, ls`

#### Scenario: Comprehensive documentation

- **WHEN** developers inspect `sandbox_utils` functions
- **THEN** each function has comprehensive docstrings including:
  - Function purpose and behavior
  - Parameter descriptions with types
  - Return value description with type
  - Usage examples
  - Security considerations (path validation, `/app` boundary)

### Requirement: Enhanced Pure-Python Package Vendoring

The Python runtime SHALL include additional vetted pure-Python packages in `vendor/site-packages/` to support common LLM use cases beyond the shell utilities library.

#### Scenario: Tier 1 packages available

- **WHEN** LLM-generated code imports vendored packages
- **THEN** the following Tier 1 packages are available via `sys.path.insert(0, '/app/site-packages')`:
  - `python-dateutil` - date and time parsing and manipulation
  - `tabulate` - pretty-printing tabular data in multiple formats
  - `jinja2` - template rendering engine with full Jinja2 syntax support

#### Scenario: Tier 2 packages available

- **WHEN** LLM-generated code imports vendored packages
- **THEN** the following Tier 2 packages are available via `sys.path.insert(0, '/app/site-packages')`:
  - `markdown` or `markdown2` - Markdown to HTML conversion
  - `jsonschema` - JSON schema validation
  - `tomli` - TOML parsing (only for Python <3.11, as 3.11+ includes `tomllib` in stdlib)

#### Scenario: Package WASM compatibility verification

- **WHEN** a new package is added to `RECOMMENDED_PACKAGES` in `sandbox/vendor.py`
- **THEN** the package has been verified to:
  - Install with `--only-binary=:all:` flag (no C extensions)
  - Import successfully in WASM sandbox environment
  - Execute basic operations within default fuel budget (2B instructions)
  - Not depend on native extensions or compiled code

#### Scenario: Package documentation

- **WHEN** developers review `sandbox/vendor.py`
- **THEN** the `RECOMMENDED_PACKAGES` list includes comments documenting:
  - Package purpose and use cases
  - Any compatibility notes or limitations
  - Whether packages have optional native extensions with pure-Python fallbacks

### Requirement: Fuel Budget Performance Targets

All `sandbox_utils` operations and vendored package usage SHALL complete within reasonable fuel budgets to enable LLM-generated workflows.

#### Scenario: Single operation fuel targets

- **WHEN** a single `sandbox_utils` operation is executed
- **THEN** the operation completes using less than 2% of default fuel budget (< 40M instructions out of 2B)
- **AND** the operation does not cause OutOfFuel trap under normal usage

#### Scenario: Complex workflow fuel targets

- **WHEN** multiple `sandbox_utils` operations are combined in a workflow
- **THEN** the combined workflow completes using less than 50% of default fuel budget (< 1B instructions)
- **AND** sufficient fuel remains for LLM-generated business logic

#### Scenario: Performance documentation

- **WHEN** developers consult fuel budget guidance
- **THEN** `docs/PYTHON_CAPABILITIES.md` includes a performance table documenting:
  - Estimated fuel costs for common operations
  - File size or data volume parameters affecting fuel consumption
  - Percentage of default fuel budget consumed
  - Guidelines for optimizing complex workflows

### Requirement: Security Boundaries Enforcement

All `sandbox_utils` operations SHALL respect WASI capability-based filesystem isolation and prevent path traversal attacks.

#### Scenario: Path validation at function entry

- **WHEN** a `sandbox_utils` function receives a path parameter
- **THEN** the path is validated using `validate_app_path()` helper
- **AND** paths are normalized to absolute paths within `/app`
- **AND** paths are resolved to eliminate symlinks and relative components

#### Scenario: Path traversal prevention

- **WHEN** a path contains `..` sequences attempting to escape `/app`
- **THEN** the function raises `ValueError` with message "Path must be within /app"
- **AND** the operation does not execute
- **AND** no file I/O occurs outside `/app` boundary

#### Scenario: Error message safety

- **WHEN** a `sandbox_utils` function encounters an error
- **THEN** error messages use paths relative to `/app` or normalized paths
- **AND** error messages do not expose host filesystem paths
- **AND** error messages do not expose system-specific information

#### Scenario: No dangerous operations

- **WHEN** reviewing `sandbox_utils` source code
- **THEN** no functions use `os.system()`, `subprocess.run()`, or equivalent shell execution
- **AND** no functions use `eval()` or `exec()` with user-controlled input
- **AND** no functions perform dynamic imports with user-controlled module names
