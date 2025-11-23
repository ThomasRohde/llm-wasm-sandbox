# Implementation Tasks

## 1. Create `sandbox_utils` Library

- [x] 1.1 Create package structure: `vendor/site-packages/sandbox_utils/__init__.py`
- [x] 1.2 Implement `files.py` module with file operation utilities
  - [x] `find(pattern, path="/app", recursive=True)` - glob-style file search
  - [x] `tree(path="/app", max_depth=None)` - directory tree visualization
  - [x] `walk(path="/app", filter_func=None)` - filtered directory traversal
  - [x] `copy_tree(src, dst)` - recursive copy with filtering
  - [x] `remove_tree(path, pattern=None)` - safe recursive deletion
- [x] 1.3 Implement `text.py` module with text processing utilities
  - [x] `grep(pattern, files, regex=True)` - search across files
  - [x] `sed(pattern, replacement, text)` - regex-based replacement
  - [x] `head(file, lines=10)` - read first N lines
  - [x] `tail(file, lines=10)` - read last N lines
  - [x] `wc(file)` - word/line/char count
  - [x] `diff(file1, file2)` - simple diff output
- [x] 1.4 Implement `data.py` module with data manipulation helpers
  - [x] `group_by(items, key_func)` - group items by key
  - [x] `filter_by(items, predicate)` - functional filtering
  - [x] `map_items(items, transform)` - functional mapping
  - [x] `sort_by(items, key_func, reverse=False)` - custom sorting
  - [x] `unique(items, key=None)` - deduplication
  - [x] `chunk(items, size)` - split into chunks
- [x] 1.5 Implement `formats.py` module with format conversions
  - [x] `csv_to_json(csv_file, output=None)` - CSV → JSON
  - [x] `json_to_csv(json_file, output=None)` - JSON → CSV
  - [x] `yaml_to_json(yaml_str)` - YAML → JSON (requires pyyaml)
  - [x] `json_to_yaml(json_str)` - JSON → YAML (requires pyyaml)
  - [x] `xml_to_dict(xml_str)` - XML → dict (using stdlib xml.etree)
- [x] 1.6 Implement `shell.py` module with shell command emulation
  - [x] `ls(path="/app", all=False, long=False)` - directory listing
  - [x] `cat(*files)` - concatenate and print files
  - [x] `touch(file)` - create empty file
  - [x] `mkdir(path, parents=True)` - create directories
  - [x] `rm(path, recursive=False, force=False)` - remove files/dirs
  - [x] `cp(src, dst, recursive=False)` - copy files/dirs
  - [x] `mv(src, dst)` - move/rename files
  - [x] `echo(text, file=None, append=False)` - print or write text
- [x] 1.7 Add comprehensive docstrings with usage examples for all functions
- [x] 1.8 Implement security validations: all paths must be within `/app`, no `..` traversal
- [x] 1.9 Export public API in `sandbox_utils/__init__.py`

## 2. Vendor Additional Pure-Python Packages

- [x] 2.1 Update `sandbox/vendor.py` RECOMMENDED_PACKAGES list
  - [x] Add `python-dateutil` for date/time parsing
  - [x] Add `tabulate` for pretty-printing tables
  - [x] Add `jinja2` for template rendering (+ MarkupSafe dependency)
  - [x] Add `markdown` for Markdown conversion
  - [x] ~~Add `jsonschema` for JSON validation~~ (INCOMPATIBLE: requires rpds-py native extensions)
  - [x] Add `tomli` (conditional: Python <3.11 only)
  - [x] Add `six` (required by python-dateutil)
  - [x] Add `attrs` (useful for data modeling)
- [x] 2.2 Test each package installation with `scripts/manage_vendor.py`
- [x] 2.3 Verify packages work in WASM environment (no C extensions)
- [x] 2.4 Test packages with fuel budgets (should complete under 2B instructions)
  - [x] python-dateutil: 1.6B ✓
  - [x] tabulate: 1.4B ✓
  - [x] jinja2: 3.9B (requires 5B fuel budget)
  - [x] markdown: 1.8B ✓
  - [x] tomli: 0.7B ✓
- [x] 2.5 Document any compatibility issues or limitations
  - [x] jsonschema incompatible (rpds-py has Rust extensions)
  - [x] jinja2 requires 5B fuel for first import
  - [x] Created PACKAGE_TESTING_RESULTS.md with detailed findings

## 3. Update Documentation

- [x] 3.1 Add "Available Python Capabilities" section to `README.md`
  - [x] Document Python Standard Library modules (categorized)
  - [x] Document vendored pure-Python packages
  - [x] Document `sandbox_utils` shell-like examples
- [x] 3.2 Update "Troubleshooting" section in `README.md`
  - [x] Add entry about using vendored packages with `sys.path.insert()`
  - [x] Add troubleshooting for vendored package import errors
  - [x] Add troubleshooting for high fuel consumption with document packages
  - [x] Add troubleshooting for `sandbox_utils` path validation errors
- [x] 3.3 Create `docs/PYTHON_CAPABILITIES.md` detailed reference
  - [x] Complete stdlib module list with categories
  - [x] Vendored package documentation with examples
  - [x] Common LLM code patterns and recipes
  - [x] Performance considerations in WASM
  - [x] Fuel budget guidance for different operations
  - [x] Package compatibility matrix
  - [x] Troubleshooting section
- [x] 3.4 Create `docs/LLM_PROMPT_TEMPLATES.md` guide
  - [x] Template for file processing tasks
  - [x] Template for data analysis tasks
  - [x] Template for text processing tasks
  - [x] Template for report generation tasks
  - [x] Template for document processing tasks
  - [x] Template for multi-step workflows
  - [x] Best practices for effective prompts
  - [x] Fuel budget quick reference

## 4. Create Demos and Examples

- [x] 4.1 Extend `demo.py` with new demo functions
  - [x] `demo_shell_utilities()` - file tree exploration, find, grep
  - [x] `demo_data_processing()` - CSV processing, grouping, filtering
- [x] 4.2 Create `examples/shell_workflows/` directory
- [x] 4.3 Create `examples/shell_workflows/file_processing.py`
  - [x] Recursive file search and filtering
  - [x] Batch file renaming
  - [x] Directory tree generation
- [x] 4.4 Create `examples/shell_workflows/text_analysis.py`
  - [x] Log file parsing and analysis
  - [x] Text search and replace
  - [x] Word frequency analysis
- [x] 4.5 Create `examples/shell_workflows/data_transformation.py`
  - [x] CSV to JSON conversion
  - [x] Data aggregation and grouping
  - [x] Report generation with tabulate
- [x] 4.6 Document each example with inline comments

## 5. Testing and Validation

- [x] 5.1 Create `tests/test_sandbox_utils.py` comprehensive test suite
  - [x] Test all `files.py` functions
  - [x] Test all `text.py` functions
  - [x] Test all `data.py` functions
  - [x] Test all `formats.py` functions
  - [x] Test all `shell.py` functions
- [x] 5.2 Test security boundaries
  - [x] Verify path validation (reject paths outside `/app`)
  - [x] Verify `..` traversal prevention
  - [x] Verify error messages don't leak host paths
- [x] 5.3 Test resource constraints
  - [x] Measure fuel consumption for common operations
  - [x] Verify operations complete within default 2B fuel budget
  - [x] Test with various file sizes and data volumes
- [x] 5.4 Test vendored packages in WASM environment
  - [x] Execute test code using each vendored package
  - [x] Verify imports work with `sys.path.insert(0, '/app/site-packages')`
- [x] 5.5 Run full test suite with coverage
  - [x] Achieve >90% coverage for `sandbox_utils` module
  - [x] Verify all tests pass in WASM sandbox

## 6. Performance Benchmarking

- [x] 6.1 Create fuel consumption benchmarks for common operations
  - [x] Benchmark `find()` with 10, 100, 1000 files
  - [x] Benchmark `grep()` with 1KB, 1MB, 10MB text
  - [x] Benchmark `csv_to_json()` with 100, 1K, 10K rows (Note: Implementation bug found, documented in results)
  - [x] Benchmark `tree()` with 10, 100, 500 directories
- [x] 6.2 Document performance guidelines in `docs/PYTHON_CAPABILITIES.md`
- [x] 6.3 Add performance budget table to documentation

## 7. Code Review and Quality Assurance

- [x] 7.1 Review all `sandbox_utils` code for security issues
  - [x] Verify no use of `os.system()`, `subprocess`, or `exec()`
  - [x] Verify no dynamic imports of user-provided module names
  - [x] Verify error handling doesn't expose sensitive information
- [x] 7.2 Review all docstrings for completeness and clarity
- [x] 7.3 Review test coverage and add missing test cases
- [x] 7.4 Run linters and type checkers (if applicable)
- [x] 7.5 Update `CHANGELOG.md` with new feature description

## Dependencies

- Tasks 2.x (vendoring packages) can run in parallel with 1.x (creating `sandbox_utils`)
- Task 3.x (documentation) depends on 1.x and 2.x completion
- Task 4.x (demos) depends on 1.x completion
- Task 5.x (testing) should run incrementally alongside 1.x-2.x
- Task 6.x (benchmarking) depends on 5.x completion

## Estimated Timeline

- **Phase 1** (`sandbox_utils` creation): 2-3 days
- **Phase 2** (vendoring packages): 1 day
- **Phase 3** (documentation): 1-2 days
- **Phase 4** (demos and examples): 1 day
- **Phase 5** (testing and validation): 1-2 days
- **Phase 6** (benchmarking): 0.5 days
- **Phase 7** (review and QA): 0.5-1 day

**Total**: 7-10 days for full implementation
