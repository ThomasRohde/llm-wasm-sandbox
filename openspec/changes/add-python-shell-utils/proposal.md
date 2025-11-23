# Change: Add Python Shell-Like Utilities Library

## Why

LLM-generated code frequently requires shell-like operations (file searching, text processing, data transformations) that are naturally expressed using shell commands. However:
- Bash/shell WASM runtimes are not viable for production use
- Asking LLMs to generate pure stdlib Python equivalents increases code complexity
- Common operations (grep, find, ls, tree) require multiple stdlib modules and verbose code

This creates friction in LLM workflows and reduces code generation quality. We need a shell-like utilities library that provides simple, LLM-friendly APIs for common operations while maintaining WASM security boundaries.

## What Changes

- **NEW**: Create `sandbox_utils` pure-Python library in `vendor/site-packages/`
  - File operations: `find()`, `tree()`, `walk()`, `copy_tree()`, `remove_tree()`
  - Text processing: `grep()`, `sed()`, `head()`, `tail()`, `wc()`, `diff()`
  - Data manipulation: `group_by()`, `filter_by()`, `map_items()`, `sort_by()`, `unique()`, `chunk()`
  - Format conversions: `csv_to_json()`, `json_to_csv()`, `yaml_to_json()`, `json_to_yaml()`, `xml_to_dict()`
  - Shell emulation: `ls()`, `cat()`, `touch()`, `mkdir()`, `rm()`, `cp()`, `mv()`, `echo()`

- **UPDATE**: Vendor additional pure-Python packages for enhanced capabilities
  - Add Tier 1 packages: `python-dateutil`, `tabulate`, `jinja2`
  - Add Tier 2 packages: `markdown`, `jsonschema`, `tomli` (conditionally for Python <3.11)

- **UPDATE**: Documentation to describe available Python capabilities
  - Add "Available Python Capabilities" section to `README.md`
  - Create comprehensive `docs/PYTHON_CAPABILITIES.md` reference guide
  - Create `docs/LLM_PROMPT_TEMPLATES.md` for effective LLM prompting

- **UPDATE**: Demos showcasing shell-like workflows
  - Extend `demo.py` with shell utilities and data processing examples
  - Create `examples/shell_workflows/` directory with realistic examples

## Impact

**Affected Specs**:
- `python-runtime-vendoring`: Adding new curated packages and `sandbox_utils` library
- `python-runtime-stdlib-utilities`: Documenting enhanced shell-like capabilities

**Affected Code**:
- `vendor/site-packages/sandbox_utils/` (new directory)
  - `__init__.py`, `files.py`, `text.py`, `data.py`, `formats.py`, `shell.py`
- `vendor/site-packages/` (new vendored packages)
- `README.md` (new section)
- `docs/PYTHON_CAPABILITIES.md` (new file)
- `docs/LLM_PROMPT_TEMPLATES.md` (new file)
- `demo.py` (extended examples)
- `examples/shell_workflows/` (new directory)
- `tests/test_sandbox_utils.py` (new test suite)

**User Impact**:
- **Before**: LLMs generate complex, verbose stdlib code or request unsupported shell commands
- **After**: LLMs use simple, shell-like Python APIs: `find("*.log")`, `grep(r"ERROR", files)`, `tree("/app")`

**Breaking Changes**: None (purely additive)

**Migration**: Not applicable (new feature)

## Success Metrics

- `sandbox_utils` provides 30+ shell-like functions
- 6+ pure-Python packages vendored and tested in WASM
- All new utilities tested with fuel budgets under 50% (< 1B instructions)
- Zero security violations (all operations respect `/app` sandbox boundary)
- Documentation covers 100% of new APIs with examples
- 5+ realistic demo workflows showcasing capabilities
