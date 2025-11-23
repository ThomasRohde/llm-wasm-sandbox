# Shell Workflows Examples

This directory contains comprehensive examples demonstrating the `sandbox_utils` library capabilities for shell-like operations in the LLM WASM Sandbox.

## Overview

The `sandbox_utils` library provides shell-like utilities for common file, text, and data operations while maintaining strict security boundaries within the `/app` sandbox. These examples show realistic workflows that LLMs can use to process data, analyze files, and generate reports.

## Examples

### 1. File Processing (`file_processing.py`)

Demonstrates file system operations using shell-like utilities.

**Features:**
- Recursive file search with glob patterns (`find`)
- Directory tree visualization (`tree`)
- Batch file operations (rename, organize)
- File filtering and cleanup

**Run:**
```bash
uv run python examples/shell_workflows/file_processing.py
```

**Key Functions Used:**
- `find()` - Search for files matching patterns
- `tree()` - Generate directory tree visualization
- `ls()` - List directory contents
- `mkdir()` - Create directories
- `touch()` - Create empty files
- `cp()` - Copy files
- `rm()` - Remove files/directories

### 2. Text Analysis (`text_analysis.py`)

Demonstrates text processing and analysis capabilities.

**Features:**
- Log file parsing and error analysis
- Text search with regex patterns (`grep`)
- Text replacement (`sed`)
- File content inspection (`head`, `tail`, `wc`)
- Word frequency analysis
- File comparison (`diff`)

**Run:**
```bash
uv run python examples/shell_workflows/text_analysis.py
```

**Key Functions Used:**
- `grep()` - Search for patterns in files
- `sed()` - Replace text using regex
- `head()` - Read first N lines
- `tail()` - Read last N lines
- `wc()` - Count words, lines, characters
- `diff()` - Compare file contents
- `cat()` - Read file contents

### 3. Data Transformation (`data_transformation.py`)

Demonstrates data processing and transformation workflows.

**Features:**
- CSV to JSON conversion (and vice versa)
- Data aggregation and grouping
- Report generation with formatted tables
- Multi-format data processing

**Run:**
```bash
uv run python examples/shell_workflows/data_transformation.py
```

**Key Functions Used:**
- `csv_to_json()` - Convert CSV to JSON format
- `json_to_csv()` - Convert JSON to CSV format
- `group_by()` - Group items by key function
- `filter_by()` - Filter items with predicate
- `sort_by()` - Sort items by key function
- `unique()` - Remove duplicates

**Additional Packages:**
- `tabulate` - Generate formatted tables for reports

## Running All Examples

To run all examples sequentially:

```bash
# File processing examples
uv run python examples/shell_workflows/file_processing.py

# Text analysis examples
uv run python examples/shell_workflows/text_analysis.py

# Data transformation examples
uv run python examples/shell_workflows/data_transformation.py
```

Or run them all at once with a script:

```bash
for file in examples/shell_workflows/*.py; do
    echo "Running $file..."
    uv run python "$file"
done
```

## Example Output

Each example produces detailed output showing:
- Step-by-step operations being performed
- Results of each operation
- Fuel consumption metrics
- File changes and data transformations

### Sample Output (File Processing):
```
====================================================
DEMO: Recursive File Search
====================================================

Created project structure

1. All Python files (.py):
   /app/project/src/main.py
   /app/project/src/utils.py
   /app/project/tests/test_main.py
   ...

[Fuel consumed: 1,234,567 instructions]
```

## Performance Notes

All examples are designed to run within the default fuel budget (2 billion instructions):

- **File Processing**: ~1-2M instructions per operation
- **Text Analysis**: ~500K-3M instructions depending on file size
- **Data Transformation**: ~1-5M instructions for CSV/JSON conversion
- **Report Generation**: ~5-10M instructions (includes tabulate formatting)

## Security Boundaries

All operations respect the `/app` sandbox boundary:

- ✅ Files can only be accessed within `/app`
- ✅ Path traversal (`..`) is blocked
- ✅ No access to host filesystem outside workspace
- ✅ All paths are validated before operations

## Integration with LLMs

These examples demonstrate patterns that LLMs can use for:

1. **File Organization**: Batch renaming, organizing files by type
2. **Log Analysis**: Parsing logs, finding errors, generating reports
3. **Data Processing**: Converting formats, aggregating data
4. **Report Generation**: Creating formatted output for humans

## Dependencies

Required packages (automatically available in sandbox):
- `sandbox_utils` - Shell-like utilities (vendored)
- `tabulate` - Table formatting (vendored)
- `python-dateutil` - Date parsing (vendored)

All packages are pre-vendored and available at `/app/site-packages` in the sandbox.

## Further Reading

- [PYTHON_CAPABILITIES.md](../../docs/PYTHON_CAPABILITIES.md) - Complete Python capabilities reference
- [LLM_PROMPT_TEMPLATES.md](../../docs/LLM_PROMPT_TEMPLATES.md) - Templates for effective LLM prompts
- [README.md](../../README.md) - Main project documentation
