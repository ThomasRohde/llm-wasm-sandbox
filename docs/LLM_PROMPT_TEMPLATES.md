# LLM Prompt Templates for WASM Sandbox

## Overview

This guide provides effective prompt templates for instructing LLMs to generate code that runs in the WASM sandbox. These templates have been tested to produce reliable, secure, and efficient code.

**Key Principles**:
1. **Explicit capability declaration**: Tell the LLM what libraries and utilities are available
2. **Path constraints**: Emphasize the `/app` working directory restriction
3. **Import pattern**: Always include the `sys.path` setup for vendored packages
4. **Error handling**: Request structured error handling and output
5. **Fuel awareness**: For complex tasks, acknowledge resource limits

---

## Template Categories

- [File Processing Tasks](#file-processing-tasks)
- [Data Analysis Tasks](#data-analysis-tasks)
- [Text Processing Tasks](#text-processing-tasks)
- [Report Generation Tasks](#report-generation-tasks)
- [Document Processing Tasks](#document-processing-tasks)
- [Multi-Step Workflows](#multi-step-workflows)

---

## File Processing Tasks

### Template 1: File Search and Filtering

```
Task: [Describe the file search task]

Environment:
- Working directory: /app (all file paths must start with /app)
- Available utilities: sandbox_utils library with find(), grep(), tree(), ls() functions
- File operations must stay within /app boundary

Requirements:
1. Use sandbox_utils.find() to locate files matching pattern
2. Filter results based on [criteria]
3. Output results as [format]

Example code structure:
```python
from sandbox_utils import find, ls

# Find files
files = find("*.ext", "/app/subdir")

# Process and output
for file in files:
    print(file)
```

Expected output: [Describe expected output format]
```

**Example Usage**:
```
Task: Find all Python files in /app that contain the word "TODO" and list them with line numbers

Environment:
- Working directory: /app (all file paths must start with /app)
- Available utilities: sandbox_utils library with find(), grep() functions
- File operations must stay within /app boundary

Requirements:
1. Use sandbox_utils.find() to locate all .py files
2. Use sandbox_utils.grep() to search for "TODO" comments
3. Output file paths with line numbers and matching lines

Example code structure:
```python
from sandbox_utils import find, grep

# Find Python files
py_files = find("*.py", "/app", recursive=True)

# Search for TODO comments
matches = grep(r"TODO", py_files, regex=True)

# Output results
for file, line_num, line in matches:
    print(f"{file}:{line_num}: {line.strip()}")
```

Expected output: Formatted list with file:line_number: content
```

### Template 2: Directory Analysis

```
Task: Analyze directory structure and provide statistics

Environment:
- Working directory: /app
- Available utilities: sandbox_utils.tree(), sandbox_utils.find(), sandbox_utils.wc()
- Python standard library: os, pathlib, collections

Requirements:
1. Generate directory tree with max_depth=[N]
2. Count files by extension
3. Calculate total size and file counts
4. Output summary as [format]

Code should:
- Use tree() for visualization
- Use find() with pattern matching
- Handle errors gracefully (non-existent paths)
```

---

## Data Analysis Tasks

### Template 3: CSV Data Processing

```
Task: [Describe CSV analysis task]

Environment:
- Working directory: /app
- Available packages (use sys.path.insert(0, '/app/site-packages')):
  - tabulate: for pretty-printing tables
  - python-dateutil: for date parsing
- Available utilities: sandbox_utils.csv_to_json(), group_by(), sort_by(), filter_by()
- Python stdlib: csv, json, collections

Requirements:
1. Read CSV from /app/[filename].csv
2. Parse and analyze data: [specific analysis]
3. Output results as [format]

Code structure:
```python
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import csv_to_json, group_by
from tabulate import tabulate
import json

# Convert CSV to JSON
csv_to_json("/app/data.csv", output="/app/data.json")

# Load and process
with open('/app/data.json') as f:
    data = json.load(f)

# Analysis logic here

# Output as table
print(tabulate(results, headers="keys", tablefmt="markdown"))
```

Expected output: [Describe expected format]
```

**Example Usage**:
```
Task: Analyze sales data from /app/sales.csv and calculate total sales by region, sorted by revenue

Environment:
- Working directory: /app
- Available packages (use sys.path.insert(0, '/app/site-packages')):
  - tabulate: for pretty-printing tables
- Available utilities: sandbox_utils.csv_to_json(), group_by(), sort_by()
- Python stdlib: csv, json

Requirements:
1. Read CSV from /app/sales.csv with columns: region, product, amount, date
2. Group sales by region and sum amounts
3. Sort by total revenue descending
4. Output as formatted markdown table

Code structure:
```python
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import csv_to_json, group_by, sort_by
from tabulate import tabulate
import json

# Convert and load data
csv_to_json("/app/sales.csv", output="/app/sales.json")
with open('/app/sales.json') as f:
    sales = json.load(f)

# Group by region
by_region = group_by(sales, lambda s: s['region'])

# Calculate totals
totals = []
for region, region_sales in by_region.items():
    total = sum(float(s['amount']) for s in region_sales)
    totals.append({'Region': region, 'Total Sales': f'${total:,.2f}', 'Count': len(region_sales)})

# Sort by revenue
sorted_totals = sort_by(totals, lambda r: float(r['Total Sales'].replace('$', '').replace(',', '')), reverse=True)

# Output
print(tabulate(sorted_totals, headers="keys", tablefmt="markdown"))
```

Expected output: Markdown table with Region, Total Sales, Count columns
```

### Template 4: JSON Data Transformation

```
Task: Transform JSON data structure

Environment:
- Working directory: /app
- Python stdlib: json
- Available utilities: sandbox_utils.filter_by(), map_items(), unique()

Requirements:
1. Read JSON from /app/[filename].json
2. Transform data: [specific transformation]
3. Write output to /app/[output].json
4. Handle missing fields gracefully

Error handling:
- Check if file exists before reading
- Validate JSON structure
- Provide meaningful error messages
```

---

## Text Processing Tasks

### Template 5: Log File Analysis

```
Task: Analyze log files and extract patterns

Environment:
- Working directory: /app
- Available utilities: sandbox_utils.find(), grep(), tail(), head()
- Python stdlib: re, collections, datetime

Requirements:
1. Find all log files matching pattern
2. Search for [error patterns/keywords]
3. Aggregate results by [category]
4. Output summary with counts and examples

Code structure:
```python
from sandbox_utils import find, grep, tail
import re
from collections import Counter

# Find log files
logs = find("*.log", "/app/logs")

# Search for patterns
errors = grep(r"ERROR|FATAL|CRITICAL", logs, regex=True)

# Analyze and group
# ... analysis logic ...

# Output summary
print(f"Total errors: {total}")
print(f"By severity: {severity_counts}")
```

Expected output: Structured summary with counts and sample error messages
```

### Template 6: Text Search and Replace

```
Task: Search and replace patterns across multiple files

Environment:
- Working directory: /app
- Available utilities: sandbox_utils.find(), sed()
- Python stdlib: re, pathlib

Requirements:
1. Find all files matching [pattern]
2. Search for [regex pattern]
3. Replace with [replacement pattern]
4. Write modified files back (or to new location)
5. Report files changed and replacements made

Safety:
- Validate paths are within /app
- Create backups before modifying
- Provide dry-run summary before changes
```

---

## Report Generation Tasks

### Template 7: HTML Report from Data

```
Task: Generate HTML report from data

Environment:
- Working directory: /app
- Available packages (use sys.path.insert(0, '/app/site-packages')):
  - jinja2: for template rendering (REQUIRES 5B FUEL BUDGET)
  - tabulate: for HTML table generation
  - markdown: for markdown to HTML conversion
- Available utilities: sandbox_utils functions for data processing

IMPORTANT: This task requires increased fuel budget due to jinja2:
```python
# When creating sandbox:
from sandbox import create_sandbox, ExecutionPolicy, RuntimeType
policy = ExecutionPolicy(fuel_budget=5_000_000_000)
sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
```

Requirements:
1. Load data from /app/[source]
2. Process and aggregate data
3. Create HTML report with:
   - Summary statistics
   - Data tables
   - [Additional visualizations if applicable]
4. Write to /app/report.html

Code structure:
```python
import sys
sys.path.insert(0, '/app/site-packages')

from jinja2 import Template
from tabulate import tabulate

# Load and process data
# ...

# Create HTML template
template = Template('''
<html>
<head>
    <title>{{ title }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
    </style>
</head>
<body>
    <h1>{{ title }}</h1>
    {{ content }}
</body>
</html>
''')

# Generate HTML content
html_table = tabulate(data, headers="keys", tablefmt="html")
report = template.render(title="Report Title", content=html_table)

# Write report
with open('/app/report.html', 'w') as f:
    f.write(report)

print("Report generated: /app/report.html")
```
```

### Template 8: Markdown Report Generation

```
Task: Create markdown report from analysis

Environment:
- Working directory: /app
- Available packages: tabulate (for markdown tables)
- Available utilities: sandbox_utils functions
- Python stdlib: datetime, statistics

Requirements:
1. Analyze data from [source]
2. Generate markdown report with:
   - Title and metadata
   - Summary section
   - Detailed tables
   - Conclusions
3. Write to /app/report.md

Use tabulate with tablefmt="markdown" for tables
Include proper markdown formatting (headers, lists, code blocks)
```

---

## Document Processing Tasks

### Template 9: Excel File Processing

```
Task: Process Excel file and extract/transform data

Environment:
- Working directory: /app
- Available packages (use sys.path.insert(0, '/app/site-packages')):
  - openpyxl: read/write Excel files (REQUIRES 5B FUEL BUDGET)
  - tabulate: for formatting output
- Available utilities: sandbox_utils.sort_by(), group_by(), filter_by()

IMPORTANT: This task requires increased fuel budget:
```python
from sandbox import create_sandbox, ExecutionPolicy, RuntimeType
policy = ExecutionPolicy(fuel_budget=5_000_000_000)
sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
```

Requirements:
1. Read Excel file from /app/[filename].xlsx
2. Extract data from sheet [sheet_name or active sheet]
3. Process data: [specific processing]
4. Output results as [format or new Excel file]

Code structure:
```python
import sys
sys.path.insert(0, '/app/site-packages')

import openpyxl
from tabulate import tabulate

# Load workbook
wb = openpyxl.load_workbook('/app/input.xlsx')
ws = wb.active

# Extract data as list of dicts
headers = [cell.value for cell in ws[1]]
data = []
for row in ws.iter_rows(min_row=2, values_only=True):
    data.append(dict(zip(headers, row)))

# Process data
# ... processing logic ...

# Output (either print or create new Excel)
print(tabulate(results, headers="keys", tablefmt="grid"))

# OR write new Excel file
wb_out = openpyxl.Workbook()
ws_out = wb_out.active
# ... write data ...
wb_out.save('/app/output.xlsx')
```
```

### Template 10: PDF Text Extraction

```
Task: Extract and analyze text from PDF files

Environment:
- Working directory: /app
- Available packages (use sys.path.insert(0, '/app/site-packages')):
  - PyPDF2: PDF reading (REQUIRES 5B FUEL BUDGET)
- Available utilities: sandbox_utils.grep(), find()

IMPORTANT: Requires increased fuel budget:
```python
policy = ExecutionPolicy(fuel_budget=5_000_000_000)
```

Requirements:
1. Read PDF from /app/[filename].pdf
2. Extract text from [all pages or specific pages]
3. Search for [patterns or keywords]
4. Output results as [format]

Code structure:
```python
import sys
sys.path.insert(0, '/app/site-packages')

from PyPDF2 import PdfReader

# Load PDF
reader = PdfReader('/app/document.pdf')

# Extract text
all_text = []
for page in reader.pages:
    text = page.extract_text()
    all_text.append(text)

# Process text
combined = '\n'.join(all_text)

# Search or analyze
# ... analysis logic ...

# Output
print(f"Extracted {len(reader.pages)} pages")
print(f"Total characters: {len(combined)}")
```

Note: Text extraction quality varies by PDF complexity
```

---

## Multi-Step Workflows

### Template 11: Data Pipeline

```
Task: Multi-step data processing pipeline

Environment:
- Working directory: /app
- Available packages: [list required packages with sys.path setup]
- Available utilities: [list sandbox_utils functions needed]
- Fuel budget: [specify if >2B needed]

Pipeline steps:
1. [Step 1: e.g., Find and validate input files]
2. [Step 2: e.g., Transform data format]
3. [Step 3: e.g., Analyze and aggregate]
4. [Step 4: e.g., Generate output report]

Requirements:
- Each step should validate inputs before processing
- Log progress at each step
- Handle errors gracefully (continue or fail-fast as appropriate)
- Create intermediate files in /app/temp/ for debugging

Code structure:
```python
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import find, mkdir
import json

# Setup
mkdir('/app/temp', parents=True)
print("Starting pipeline...")

# Step 1: Discovery
print("Step 1: Finding input files...")
input_files = find("*.csv", "/app/input")
print(f"  Found {len(input_files)} files")

# Step 2: Transformation
print("Step 2: Transforming data...")
# ... transformation logic ...
print(f"  Transformed {count} records")

# Step 3: Analysis
print("Step 3: Analyzing...")
# ... analysis logic ...
print(f"  Analysis complete")

# Step 4: Output
print("Step 4: Generating output...")
# ... output logic ...
print(f"  Output written to /app/output/")

print("Pipeline complete!")
```

Expected output: Step-by-step progress log with final summary
```

### Template 12: Batch File Processing

```
Task: Process multiple files with same operation

Environment:
- Working directory: /app
- Available utilities: sandbox_utils.find(), [other utilities]
- Available packages: [if needed]

Requirements:
1. Find all files matching [pattern]
2. Apply operation to each file: [operation description]
3. Track successes and failures
4. Generate summary report

Error handling:
- Continue on individual file errors
- Log each error with filename
- Report success rate at end

Code structure:
```python
from sandbox_utils import find

# Find files
files = find("[pattern]", "/app/[directory]")

# Process each file
results = {"success": 0, "failed": 0, "errors": []}

for file in files:
    try:
        # Process file
        # ... processing logic ...
        results["success"] += 1
    except Exception as e:
        results["failed"] += 1
        results["errors"].append(f"{file}: {str(e)}")

# Summary
print(f"Processed {len(files)} files")
print(f"Success: {results['success']}, Failed: {results['failed']}")
if results["errors"]:
    print("\nErrors:")
    for error in results["errors"]:
        print(f"  - {error}")
```
```

---

## Best Practices for Prompts

### 1. Always Declare Environment

**Good**:
```
Environment:
- Working directory: /app (all paths must be within /app)
- Available packages: tabulate, openpyxl (use sys.path.insert(0, '/app/site-packages'))
- Available utilities: sandbox_utils.find(), grep(), csv_to_json()
- Fuel budget: 5B (due to openpyxl import)
```

**Bad**:
```
Use Python to process the Excel file
```

### 2. Specify Path Constraints

**Good**:
```
Requirements:
- All file paths must start with /app
- Input file: /app/data/input.csv
- Output directory: /app/output/
- No access to paths outside /app
```

**Bad**:
```
Read the CSV file and write output
```

### 3. Include Import Pattern for Vendored Packages

**Good**:
```python
import sys
sys.path.insert(0, '/app/site-packages')

from tabulate import tabulate
import openpyxl
```

**Bad**:
```python
import openpyxl  # Will fail - package not in sys.path
```

### 4. Request Structured Output

**Good**:
```
Expected output:
- Summary line: "Processed X files, Y errors"
- Table of results in markdown format
- List of any error messages
```

**Bad**:
```
Print the results
```

### 5. Specify Error Handling Strategy

**Good**:
```
Error handling:
- Validate input file exists before processing
- If CSV is malformed, skip and log error
- Continue processing remaining files on error
- Report all errors at end with file names
```

**Bad**:
```
Handle errors appropriately
```

### 6. Include Example Code Structure

**Good**:
```
Code structure:
```python
from sandbox_utils import find, grep

# Step 1: Find files
files = find("*.log", "/app/logs")

# Step 2: Search patterns
matches = grep(r"ERROR", files)

# Step 3: Output results
for file, line_num, line in matches:
    print(f"{file}:{line_num}: {line}")
```
```

**Bad**:
```
Write code to find errors in log files
```

### 7. Warn About Fuel Budget Requirements

**Good**:
```
IMPORTANT: This task requires increased fuel budget due to openpyxl:
```python
from sandbox import create_sandbox, ExecutionPolicy, RuntimeType
policy = ExecutionPolicy(fuel_budget=5_000_000_000)
sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
```
```

**Bad**:
```
Use openpyxl to process Excel files
```

---

## Quick Reference: Fuel Requirements

Include this table in prompts when relevant:

| Package/Operation | Fuel Required | Note |
|------------------|---------------|------|
| Standard library imports | Default (2B) | ✅ No special setup |
| tabulate, markdown, attrs | Default (2B) | ✅ No special setup |
| python-dateutil, tomli | Default (2B) | ✅ No special setup |
| **openpyxl, PyPDF2, jinja2** | **5B** | ⚠️ Requires `ExecutionPolicy(fuel_budget=5_000_000_000)` |
| Most sandbox_utils ops | <100M | ✅ Negligible fuel cost |
| csv_to_json (10K rows) | ~50M | ✅ Well within default |
| grep (1MB text) | ~20M | ✅ Well within default |

---

## See Also

- [PYTHON_CAPABILITIES.md](PYTHON_CAPABILITIES.md) - Complete reference of available capabilities
- [README.md](../README.md) - Main project documentation
- [examples/](../examples/) - Working code examples
