# Python Capabilities in WASM Sandbox

## Overview

The LLM WASM Sandbox provides a rich Python 3.11+ environment with:
- **Full standard library** (subject to WASI filesystem limitations)
- **30+ vendored pure-Python packages** for document processing, text manipulation, and data analysis
- **`sandbox_utils` library** with shell-like APIs optimized for LLM code generation

This document provides a comprehensive reference for all available capabilities.

---

## Python Standard Library

### Complete Module Reference

The CPython WASM runtime includes the full standard library, organized by category:

#### File & I/O Operations

| Module | Description | Example Use Case |
|--------|-------------|------------------|
| `pathlib` | Object-oriented filesystem paths | `Path('/app/data').glob('*.json')` |
| `os.path` | Common pathname manipulations | `os.path.join('/app', 'file.txt')` |
| `shutil` | High-level file operations | `shutil.copy('/app/src.txt', '/app/dst.txt')` |
| `glob` | Unix-style pathname pattern expansion | `glob.glob('/app/**/*.py', recursive=True)` |
| `tempfile` | Generate temporary files/directories | `tempfile.NamedTemporaryFile(dir='/app')` |
| `fileinput` | Iterate over lines from multiple input files | `fileinput.input(files=['/app/f1.txt', '/app/f2.txt'])` |
| `io` | Core tools for working with streams | `io.StringIO()`, `io.BytesIO()` |

**Security Note**: All file operations are confined to `/app` by WASI capabilities. Attempts to access paths outside `/app` will fail with permission errors.

#### Text & Data Processing

| Module | Description | Example Use Case |
|--------|-------------|------------------|
| `re` | Regular expression operations | `re.findall(r'\d+', text)` |
| `json` | JSON encoder/decoder | `json.loads(data)`, `json.dumps(obj)` |
| `csv` | CSV file reading/writing | `csv.DictReader(file)` |
| `xml.etree.ElementTree` | XML parsing and creation | `ET.parse('/app/data.xml')` |
| `tomllib` (3.11+) | TOML parser (stdlib) | `tomllib.load(f)` |
| `configparser` | Configuration file parser | `.ini` file parsing |
| `string` | Common string operations | `string.Template()` |
| `textwrap` | Text wrapping and filling | `textwrap.fill(text, width=80)` |
| `difflib` | Helpers for computing deltas | `difflib.unified_diff(a, b)` |

#### Data Structures & Algorithms

| Module | Description | Example Use Case |
|--------|-------------|------------------|
| `collections` | Container datatypes | `Counter()`, `defaultdict()`, `deque()` |
| `collections.abc` | Abstract base classes for containers | Type checking, protocol validation |
| `itertools` | Functions creating iterators | `chain()`, `groupby()`, `permutations()` |
| `functools` | Higher-order functions | `@lru_cache`, `reduce()`, `partial()` |
| `operator` | Standard operators as functions | `operator.itemgetter()`, `attrgetter()` |
| `heapq` | Heap queue algorithm | Priority queue implementation |
| `bisect` | Array bisection algorithm | Maintain sorted lists |
| `array` | Efficient arrays of numeric values | Space-efficient storage |

#### Date, Time & Calendar

| Module | Description | Example Use Case |
|--------|-------------|------------------|
| `datetime` | Basic date and time types | `datetime.now()`, `timedelta()` |
| `time` | Time access and conversions | `time.time()`, `time.sleep()` |
| `calendar` | General calendar-related functions | `calendar.monthrange(2024, 1)` |
| `zoneinfo` (3.9+) | IANA time zone support | `ZoneInfo('America/New_York')` |

**Note**: `time.sleep()` consumes fuel but cannot be interrupted by fuel exhaustion during the sleep itself.

#### Mathematics & Statistics

| Module | Description | Example Use Case |
|--------|-------------|------------------|
| `math` | Mathematical functions | `math.sqrt()`, `math.ceil()`, trigonometry |
| `statistics` | Statistical functions | `mean()`, `median()`, `stdev()` |
| `random` | Generate pseudo-random numbers | `random.randint()`, `random.choice()` |
| `decimal` | Decimal fixed-point arithmetic | Financial calculations |
| `fractions` | Rational numbers | Exact fractional arithmetic |
| `cmath` | Mathematical functions for complex numbers | Complex number operations |

#### Text Processing & Encoding

| Module | Description | Example Use Case |
|--------|-------------|------------------|
| `base64` | Base16, Base32, Base64 encoding | `base64.b64encode(data)` |
| `binascii` | Binary/ASCII conversions | Hex encoding/decoding |
| `hashlib` | Secure hashes and message digests | `hashlib.sha256(data).hexdigest()` |
| `hmac` | Keyed-hashing for message authentication | HMAC-SHA256 signatures |
| `secrets` | Generate secure random numbers | Cryptographic tokens |
| `codecs` | Codec registry and base classes | Text encoding/decoding |
| `unicodedata` | Unicode database | Character properties, normalization |

#### Data Compression

| Module | Description | Example Use Case |
|--------|-------------|------------------|
| `zipfile` | Work with ZIP archives | `zipfile.ZipFile('/app/archive.zip')` |
| `tarfile` | Read/write tar archive files | `tarfile.open('/app/archive.tar')` |
| `gzip` | Support for gzip files | `gzip.open('/app/file.gz')` |
| `bz2` | Support for bzip2 compression | `bz2.open('/app/file.bz2')` |
| `lzma` | Compression using LZMA algorithm | `lzma.open('/app/file.xz')` |

#### Type Hints & Inspection

| Module | Description | Example Use Case |
|--------|-------------|------------------|
| `typing` | Support for type hints | `List[int]`, `Dict[str, Any]`, `Optional[str]` |
| `types` | Dynamic type creation | `types.SimpleNamespace()` |
| `inspect` | Inspect live objects | `inspect.signature(func)` |
| `dataclasses` (3.7+) | Data class decorator | `@dataclass` for structured data |
| `enum` | Support for enumerations | `class Color(Enum): RED = 1` |

#### Utilities & Miscellaneous

| Module | Description | Example Use Case |
|--------|-------------|------------------|
| `copy` | Shallow and deep copy operations | `copy.deepcopy(obj)` |
| `pickle` | Python object serialization | Serialize Python objects (use with caution) |
| `shelve` | Python object persistence | Key-value database backed by pickle |
| `sqlite3` | DB-API 2.0 interface for SQLite | In-memory or file-based SQL database |
| `uuid` | UUID objects | `uuid.uuid4()` for unique identifiers |
| `warnings` | Warning control | Issue and filter warnings |
| `logging` | Logging facility for Python | Structured logging (output to `/app/logs`) |

### Standard Library Limitations in WASM

**Not Available** (due to WASI/WASM constraints):
- `socket`, `http.client`, `urllib.request` - No networking in baseline WASI
- `subprocess` - Cannot spawn child processes
- `threading`, `multiprocessing` - Single-threaded execution only
- `signal` - Limited signal handling in WASM
- `pwd`, `grp` - No user/group database access
- `fcntl`, `termios` - Unix-specific I/O control not available

**Limited Functionality**:
- `os` module: Only filesystem operations within `/app` are permitted
- `sys` module: Some attributes may differ in WASM environment

---

## Vendored Pure-Python Packages

### Installation & Usage

All vendored packages are pre-installed in `vendor/site-packages/` and mounted read-only at `/data/site-packages` (shared across all sessions for efficiency).

**Standard import pattern** (automatically injected by sandbox):
```python
# The sandbox automatically injects this at the start of your code:
# sys.path.insert(0, '/data/site-packages')

# You can import vendored packages directly:
from tabulate import tabulate
import openpyxl
```

### Package Reference

#### Document Processing

##### Excel Files

**openpyxl** - Read and write Excel 2010+ (.xlsx) files
```python
from openpyxl import load_workbook, Workbook

# Read Excel file
wb = load_workbook('/app/data.xlsx')
ws = wb.active
for row in ws.iter_rows(values_only=True):
    print(row)

# Write Excel file
wb = Workbook()
ws = wb.active
ws['A1'] = 'Hello'
ws['B1'] = 'World'
wb.save('/app/output.xlsx')
```
- **Fuel**: ~3-5B instructions (first import)
- **Dependencies**: et_xmlfile (auto-installed)

**XlsxWriter** - Write Excel files (write-only, lighter than openpyxl)
```python
import xlsxwriter

workbook = xlsxwriter.Workbook('/app/output.xlsx')
worksheet = workbook.add_worksheet()

worksheet.write('A1', 'Hello')
worksheet.write('B1', 'World')

workbook.close()
```
- **Fuel**: ~2-3B instructions (first import)
- **Use case**: When you only need to create Excel files (not read)

##### PDF Files

**PyPDF2** - Read, write, and merge PDF files
```python
from PyPDF2 import PdfReader, PdfWriter, PdfMerger

# Read PDF
reader = PdfReader('/app/input.pdf')
print(f"Pages: {len(reader.pages)}")
text = reader.pages[0].extract_text()

# Merge PDFs
merger = PdfMerger()
merger.append('/app/file1.pdf')
merger.append('/app/file2.pdf')
merger.write('/app/merged.pdf')
```
- **Fuel**: ~3B instructions (first import)
- **Note**: Text extraction may be limited for complex PDFs

##### OpenDocument Format

**odfpy** - Read and write ODF files (.odt, .ods, .odp)
```python
from odf import opendocument, text, table
from odf.opendocument import load

# Create ODS spreadsheet
doc = opendocument.OpenDocumentSpreadsheet()
t = table.Table(name="Sheet1")
# Add rows and cells...
doc.spreadsheet.addElement(t)
doc.save('/app/output.ods')
```
- **Fuel**: ~2-4B instructions (first import)
- **Use case**: LibreOffice/OpenOffice document format

##### Word Documents

**mammoth** - Convert Word (.docx) to HTML/Markdown
```python
import mammoth

# Convert to HTML
with open('/app/document.docx', 'rb') as docx_file:
    result = mammoth.convert_to_html(docx_file)
    html = result.value
    
# Convert to Markdown
with open('/app/document.docx', 'rb') as docx_file:
    result = mammoth.convert_to_markdown(docx_file)
    markdown = result.value
```
- **Fuel**: ~2B instructions (first import)
- **Use case**: Read-only .docx parsing (alternative to python-docx)

#### Text Processing & Templates

**tabulate** - Pretty-print tabular data
```python
from tabulate import tabulate

data = [
    ["Alice", 25, "Engineer"],
    ["Bob", 30, "Designer"],
    ["Charlie", 35, "Manager"]
]

# ASCII table
print(tabulate(data, headers=["Name", "Age", "Role"]))

# Markdown table
print(tabulate(data, headers=["Name", "Age", "Role"], tablefmt="markdown"))

# HTML table
html = tabulate(data, headers=["Name", "Age", "Role"], tablefmt="html")
```
- **Fuel**: ~1.4B instructions (first import)
- **Formats**: ascii, markdown, html, latex, grid, fancy_grid, rst, and more

**jinja2** + **MarkupSafe** - Template rendering
```python
from jinja2 import Template

template = Template("""
<html>
<body>
  <h1>{{ title }}</h1>
  <ul>
  {% for item in items %}
    <li>{{ item }}</li>
  {% endfor %}
  </ul>
</body>
</html>
""")

html = template.render(title="My List", items=["Alice", "Bob", "Charlie"])
```
- **Fuel**: ~4B instructions (first import) ⚠️ **Requires 5B fuel budget**
- **Use case**: HTML, code, or text generation from templates
- **Security**: Auto-escapes HTML by default (via MarkupSafe)

**markdown** - Markdown to HTML conversion
```python
import markdown

html = markdown.markdown("""
# Hello World

This is **bold** and this is *italic*.

- Item 1
- Item 2
""")
```
- **Fuel**: ~1.8B instructions (first import)
- **Extensions**: Supports tables, code highlighting, etc.

#### Date & Time Extensions

**python-dateutil** - Advanced date/time parsing and manipulation
```python
from dateutil import parser, relativedelta
from datetime import datetime

# Parse natural language dates
dt = parser.parse("2024-03-15 14:30:00")

# Date arithmetic
now = datetime.now()
next_month = now + relativedelta.relativedelta(months=1)
three_days_ago = now - relativedelta.relativedelta(days=3)

# Recurring dates (rrule)
from dateutil.rrule import rrule, DAILY
dates = list(rrule(DAILY, count=7, dtstart=datetime.now()))
```
- **Fuel**: ~1.6B instructions (first import)
- **Dependencies**: Requires `six` package

#### Data Modeling

**attrs** - Classes without boilerplate
```python
import attrs

@attrs.define
class User:
    name: str
    age: int
    email: str = attrs.field(default=None)
    
    @email.validator
    def check_email(self, attribute, value):
        if value and '@' not in value:
            raise ValueError("Invalid email")

user = User(name="Alice", age=25, email="alice@example.com")
print(attrs.asdict(user))
```
- **Fuel**: ~1B instructions (first import)
- **Use case**: Structured data classes with validation

#### HTTP & Encoding

**certifi**, **charset-normalizer**, **idna**, **urllib3**
```python
# Note: Actual HTTP requests will fail (no networking in WASI)
# But encoding utilities work fine

from charset_normalizer import from_bytes

# Detect text encoding
result = from_bytes(b'\xe4\xbd\xa0\xe5\xa5\xbd')
print(result.best().encoding)  # 'utf-8'

# IDNA encoding
import idna
encoded = idna.encode('münchen.de')  # b'xn--mnchen-3ya.de'
```
- **Fuel**: ~1-2B instructions (varies by package)
- **Use case**: Text encoding detection, internationalized domain names

#### Compatibility Utilities

**six** - Python 2/3 compatibility
```python
import six

if six.PY3:
    print("Running Python 3")

# Useful utilities even in Python 3
six.text_type  # str in Python 3
six.binary_type  # bytes in Python 3
```
- **Fuel**: ~0.5B instructions
- **Note**: Required dependency for python-dateutil

**tomli** - TOML parser (Python <3.11)
```python
import tomli  # Use tomllib on Python 3.11+

with open('/app/config.toml', 'rb') as f:
    config = tomli.load(f)
```
- **Fuel**: ~0.7B instructions
- **Note**: Only needed for Python <3.11; use stdlib `tomllib` on 3.11+

### Package Compatibility Matrix

| Package | Pure Python? | Fuel (First Import) | Compatible? | Notes |
|---------|-------------|---------------------|-------------|-------|
| openpyxl | ✅ Yes | 3-5B | ✅ Yes | Requires 5B fuel budget |
| XlsxWriter | ✅ Yes | 2-3B | ✅ Yes | - |
| PyPDF2 | ✅ Yes | ~3B | ✅ Yes | - |
| odfpy | ✅ Yes | 2-4B | ✅ Yes | - |
| mammoth | ✅ Yes | ~2B | ✅ Yes | - |
| tabulate | ✅ Yes | ~1.4B | ✅ Yes | - |
| jinja2 | ✅ Yes | ~4B | ✅ Yes | Requires 5B fuel budget |
| markdown | ✅ Yes | ~1.8B | ✅ Yes | - |
| python-dateutil | ✅ Yes | ~1.6B | ✅ Yes | Requires `six` |
| attrs | ✅ Yes | ~1B | ✅ Yes | - |
| certifi | ✅ Yes | ~0.5B | ✅ Yes | - |
| charset-normalizer | ✅ Yes | ~1B | ✅ Yes | - |
| idna | ✅ Yes | ~0.5B | ✅ Yes | - |
| urllib3 | ✅ Yes | ~1.5B | ⚠️ Partial | No networking, encoding works |
| six | ✅ Yes | ~0.5B | ✅ Yes | - |
| tomli | ✅ Yes | ~0.7B | ✅ Yes | Python <3.11 only |
| **jsonschema** | ❌ No | N/A | ❌ No | Requires rpds-py (Rust) |
| **python-docx** | ❌ No | N/A | ❌ No | Requires lxml (C) |
| **pdfminer.six** | ❌ No | N/A | ❌ No | Requires cryptography (C) |

---

## `sandbox_utils` Library

### Overview

Purpose-built shell-like utilities optimized for LLM code generation. All functions:
- ✅ Enforce `/app` path validation
- ✅ Reject `..` traversal attempts
- ✅ Are pure-Python (WASM-compatible)
- ✅ Complete within default 2B fuel budget

### File Operations (`sandbox_utils.files`)

#### `find(pattern, path="/app", recursive=True)`
Find files matching glob pattern.

```python
from sandbox_utils import find

# Find all Python files
files = find("*.py", "/app", recursive=True)

# Find JSON files in specific directory (non-recursive)
configs = find("*.json", "/app/config", recursive=False)

# Find files with multiple extensions (use custom filter)
for file in find("*", "/app"):
    if file.suffix in ['.txt', '.md', '.rst']:
        print(file)
```

**Returns**: `list[Path]`  
**Fuel**: ~5M per 100 files

#### `tree(path="/app", max_depth=None)`
Display directory tree structure.

```python
from sandbox_utils import tree

# Full tree
print(tree("/app"))

# Limited depth
print(tree("/app/data", max_depth=2))
```

**Returns**: `str` (formatted tree)  
**Fuel**: ~10M per 500 directories

#### `walk(path="/app", filter_func=None)`
Filtered directory traversal iterator.

```python
from sandbox_utils import walk

# Iterate all files
for file_path in walk("/app"):
    print(file_path)

# Filter by extension
for py_file in walk("/app", filter_func=lambda p: p.suffix == ".py"):
    print(py_file)

# Filter by size
import os
for large_file in walk("/app", filter_func=lambda p: p.stat().st_size > 1024*1024):
    print(f"{large_file}: {p.stat().st_size} bytes")
```

**Returns**: `Iterator[Path]`  
**Fuel**: Depends on filter complexity

#### `copy_tree(src, dst)`
Recursively copy directory tree.

```python
from sandbox_utils import copy_tree

# Backup directory
copy_tree("/app/data", "/app/data_backup")
```

**Returns**: `None`  
**Fuel**: Linear in file count

#### `remove_tree(path, pattern=None)`
Safe recursive deletion with optional filtering.

```python
from sandbox_utils import remove_tree

# Remove entire directory
remove_tree("/app/temp")

# Remove only matching files
remove_tree("/app/logs", pattern="*.log")
```

**Returns**: `None`  
**Fuel**: Linear in file count  
**Security**: Cannot remove paths outside `/app`

### Text Processing (`sandbox_utils.text`)

#### `grep(pattern, files, regex=True)`
Search for pattern across files.

```python
from sandbox_utils import grep, find

# Search for errors in log files
log_files = find("*.log", "/app/logs")
errors = grep(r"ERROR|FATAL", log_files, regex=True)

# Output format: list of (file, line_number, line_content)
for file, line_num, line in errors:
    print(f"{file}:{line_num}: {line}")
```

**Returns**: `list[tuple[str, int, str]]` (file, line_number, line_content)  
**Fuel**: ~20M per 1MB text (depends on regex complexity)

#### `sed(pattern, replacement, text)`
Regex-based text replacement.

```python
from sandbox_utils import sed

text = "foo123 bar456 foo789"
result = sed(r"foo(\d+)", r"baz\1", text)
# Result: "baz123 bar456 baz789"
```

**Returns**: `str`  
**Fuel**: Depends on text size and regex complexity

#### `head(file, lines=10)`
Read first N lines of file.

```python
from sandbox_utils import head

# First 10 lines
content = head("/app/large_file.txt")

# First 100 lines
content = head("/app/data.csv", lines=100)
```

**Returns**: `str`  
**Fuel**: ~1M for 10 lines (constant time)

#### `tail(file, lines=10)`
Read last N lines of file.

```python
from sandbox_utils import tail

# Last 10 lines (useful for logs)
recent_logs = tail("/app/application.log", lines=50)
```

**Returns**: `str`  
**Fuel**: Linear in file size (must seek from end)

#### `wc(file)`
Word, line, and character count.

```python
from sandbox_utils import wc

stats = wc("/app/document.txt")
print(f"Lines: {stats['lines']}, Words: {stats['words']}, Chars: {stats['chars']}")
```

**Returns**: `dict[str, int]` with keys `lines`, `words`, `chars`  
**Fuel**: ~25M per 1MB file

#### `diff(file1, file2)`
Simple diff output between two files.

```python
from sandbox_utils import diff

changes = diff("/app/old_version.txt", "/app/new_version.txt")
print(changes)
```

**Returns**: `str` (unified diff format)  
**Fuel**: Depends on file sizes

### Data Manipulation (`sandbox_utils.data`)

#### `group_by(items, key_func)`
Group items by key function.

```python
from sandbox_utils import group_by

users = [
    {"name": "Alice", "country": "US"},
    {"name": "Bob", "country": "UK"},
    {"name": "Charlie", "country": "US"}
]

by_country = group_by(users, lambda u: u["country"])
# Result: {"US": [Alice, Charlie], "UK": [Bob]}
```

**Returns**: `dict[Any, list[Any]]`

#### `filter_by(items, predicate)`
Functional filtering.

```python
from sandbox_utils import filter_by

numbers = [1, 2, 3, 4, 5, 6]
evens = filter_by(numbers, lambda n: n % 2 == 0)
# Result: [2, 4, 6]
```

**Returns**: `list[Any]`

#### `map_items(items, transform)`
Functional mapping.

```python
from sandbox_utils import map_items

numbers = [1, 2, 3, 4]
squared = map_items(numbers, lambda n: n ** 2)
# Result: [1, 4, 9, 16]
```

**Returns**: `list[Any]`

#### `sort_by(items, key_func, reverse=False)`
Custom sorting.

```python
from sandbox_utils import sort_by

users = [
    {"name": "Alice", "age": 30},
    {"name": "Bob", "age": 25},
    {"name": "Charlie", "age": 35}
]

by_age = sort_by(users, lambda u: u["age"])
oldest_first = sort_by(users, lambda u: u["age"], reverse=True)
```

**Returns**: `list[Any]`

#### `unique(items, key=None)`
Deduplication with optional key function.

```python
from sandbox_utils import unique

# Simple deduplication
numbers = [1, 2, 2, 3, 3, 3, 4]
unique_nums = unique(numbers)
# Result: [1, 2, 3, 4]

# Dedup by key
users = [
    {"id": 1, "name": "Alice"},
    {"id": 2, "name": "Bob"},
    {"id": 1, "name": "Alice (duplicate)"}
]
unique_users = unique(users, key=lambda u: u["id"])
# Result: [Alice, Bob]
```

**Returns**: `list[Any]`

#### `chunk(items, size)`
Split items into fixed-size chunks.

```python
from sandbox_utils import chunk

data = list(range(10))
for batch in chunk(data, size=3):
    print(batch)
# Output: [0,1,2], [3,4,5], [6,7,8], [9]
```

**Returns**: `Iterator[list[Any]]`

### Format Conversions (`sandbox_utils.formats`)

#### `csv_to_json(csv_file, output=None)`
Convert CSV to JSON.

```python
from sandbox_utils import csv_to_json

# Convert and return as string
json_str = csv_to_json("/app/data.csv")

# Convert and write to file
csv_to_json("/app/data.csv", output="/app/data.json")
```

**Returns**: `str` (if `output=None`) or `None` (if writing to file)  
**Fuel**: ~50M per 10K rows

#### `json_to_csv(json_file, output=None)`
Convert JSON (array of objects) to CSV.

```python
from sandbox_utils import json_to_csv

# Convert and return as string
csv_str = json_to_csv("/app/data.json")

# Convert and write to file
json_to_csv("/app/data.json", output="/app/data.csv")
```

**Returns**: `str` (if `output=None`) or `None` (if writing to file)  
**Fuel**: ~50M per 10K rows

#### `yaml_to_json(yaml_str)` / `json_to_yaml(json_str)`
YAML ↔ JSON conversion.

**Note**: Requires `pyyaml` to be vendored (not included by default - has optional C extensions).

```python
from sandbox_utils import yaml_to_json, json_to_yaml

yaml = """
name: Alice
age: 30
skills:
  - Python
  - JavaScript
"""

json_str = yaml_to_json(yaml)
# Back to YAML
yaml_str = json_to_yaml(json_str)
```

**Returns**: `str`

#### `xml_to_dict(xml_str)`
Convert XML to Python dict.

```python
from sandbox_utils import xml_to_dict

xml = """
<root>
  <person id="1">
    <name>Alice</name>
    <age>30</age>
  </person>
</root>
"""

data = xml_to_dict(xml)
# Result: {'person': {'@id': '1', 'name': 'Alice', 'age': '30'}}
```

**Returns**: `dict[str, Any]`  
**Note**: Uses stdlib `xml.etree.ElementTree`

### Shell Emulation (`sandbox_utils.shell`)

#### `ls(path="/app", all=False, long=False)`
List directory contents.

```python
from sandbox_utils import ls

# Simple listing (returns list of filenames)
files = ls("/app")

# Include hidden files
all_files = ls("/app", all=True)

# Long format (returns list of dicts with metadata)
details = ls("/app", long=True)
for item in details:
    print(f"{item['name']}: {item['size']} bytes, {item['modified']}")
```

**Returns**: `list[str]` (simple) or `list[dict]` (long format)  
**Long format dict keys**: `name`, `size`, `type`, `modified`, `permissions`

#### `cat(*files)`
Concatenate and print files.

```python
from sandbox_utils import cat

# Single file
content = cat("/app/file.txt")

# Multiple files
combined = cat("/app/file1.txt", "/app/file2.txt", "/app/file3.txt")
```

**Returns**: `str`

#### `touch(file)`
Create empty file (update timestamp if exists).

```python
from sandbox_utils import touch

touch("/app/newfile.txt")
```

**Returns**: `None`

#### `mkdir(path, parents=True)`
Create directories.

```python
from sandbox_utils import mkdir

# Create single directory
mkdir("/app/data")

# Create nested directories
mkdir("/app/data/logs/2024", parents=True)
```

**Returns**: `None`

#### `rm(path, recursive=False, force=False)`
Remove files or directories.

```python
from sandbox_utils import rm

# Remove file
rm("/app/temp.txt")

# Remove directory and contents
rm("/app/temp_dir", recursive=True)

# Force removal (ignore errors)
rm("/app/maybe_exists.txt", force=True)
```

**Returns**: `None`  
**Security**: Cannot remove paths outside `/app`

#### `cp(src, dst, recursive=False)`
Copy files or directories.

```python
from sandbox_utils import cp

# Copy file
cp("/app/source.txt", "/app/dest.txt")

# Copy directory
cp("/app/source_dir", "/app/dest_dir", recursive=True)
```

**Returns**: `None`

#### `mv(src, dst)`
Move or rename files.

```python
from sandbox_utils import mv

# Rename file
mv("/app/old_name.txt", "/app/new_name.txt")

# Move file to directory
mv("/app/file.txt", "/app/archive/file.txt")
```

**Returns**: `None`

#### `echo(text, file=None, append=False)`
Print or write text.

```python
from sandbox_utils import echo

# Print to stdout
echo("Hello, World!")

# Write to file (overwrite)
echo("Log entry", file="/app/log.txt")

# Append to file
echo("Another entry", file="/app/log.txt", append=True)
```

**Returns**: `str` (if `file=None`) or `None` (if writing to file)

---

## Common LLM Code Patterns

### Pattern 1: File Processing Workflow

```python
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import find, grep, head, tail
from tabulate import tabulate

# Find all log files
log_files = find("*.log", "/app/logs")

# Search for errors
errors = grep(r"ERROR|FATAL", log_files)

# Group by file
from sandbox_utils import group_by
errors_by_file = group_by(errors, lambda e: e[0])

# Create summary table
summary = []
for file, matches in errors_by_file.items():
    summary.append({
        "File": file,
        "Error Count": len(matches),
        "First Error": head(file, lines=1) if matches else "N/A"
    })

print(tabulate(summary, headers="keys", tablefmt="markdown"))
```

### Pattern 2: Data Transformation

```python
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import csv_to_json, find
import json

# Convert all CSV files to JSON
csv_files = find("*.csv", "/app/data")

for csv_file in csv_files:
    json_file = str(csv_file).replace('.csv', '.json')
    csv_to_json(str(csv_file), output=json_file)
    
    # Process JSON
    with open(json_file) as f:
        data = json.load(f)
    
    # Analyze data
    print(f"Processed {csv_file}: {len(data)} records")
```

### Pattern 3: Report Generation

```python
import sys
sys.path.insert(0, '/app/site-packages')

from jinja2 import Template
from sandbox_utils import find, wc
from tabulate import tabulate

# Analyze all documents
docs = find("*.txt", "/app/documents")

stats = []
for doc in docs:
    counts = wc(str(doc))
    stats.append({
        "Document": doc.name,
        "Lines": counts["lines"],
        "Words": counts["words"],
        "Characters": counts["chars"]
    })

# Generate HTML report
template = Template("""
<html>
<head><title>Document Statistics</title></head>
<body>
  <h1>Document Analysis Report</h1>
  <p>Total documents: {{ total }}</p>
  {{ table }}
</body>
</html>
""")

html_table = tabulate(stats, headers="keys", tablefmt="html")
report = template.render(total=len(stats), table=html_table)

with open('/app/report.html', 'w') as f:
    f.write(report)
```

### Pattern 4: Excel Data Processing

```python
import sys
sys.path.insert(0, '/app/site-packages')

import openpyxl
from sandbox_utils import sort_by, filter_by, group_by
from tabulate import tabulate

# Load Excel data
wb = openpyxl.load_workbook('/app/sales.xlsx')
ws = wb.active

# Extract data as list of dicts
headers = [cell.value for cell in ws[1]]
data = []
for row in ws.iter_rows(min_row=2, values_only=True):
    data.append(dict(zip(headers, row)))

# Analyze sales
sales_by_region = group_by(data, lambda r: r['Region'])
top_sales = sort_by(data, lambda r: r['Amount'], reverse=True)[:10]

# Create summary
summary = []
for region, sales in sales_by_region.items():
    total = sum(s['Amount'] for s in sales)
    summary.append({
        'Region': region,
        'Sales': len(sales),
        'Total': f"${total:,.2f}"
    })

# Print report
print(tabulate(summary, headers="keys", tablefmt="grid"))
print("\nTop 10 Sales:")
print(tabulate(top_sales, headers="keys", tablefmt="grid"))
```

---

## Performance Guidelines

### Fuel Budget Reference Table

Quick reference for fuel requirements across different operations and packages. This table helps you set appropriate fuel budgets for your MCP tool calls or sandbox executions.

#### Package Import Fuel Requirements

| Package | First Import | Subsequent Imports (Cached) | Minimum Budget | Recommended Budget |
|---------|--------------|----------------------------|----------------|-------------------|
| **Document Processing** |||||
| openpyxl | 5-7B | <100M | 10B | 10B |
| PyPDF2 | 5-6B | <100M | 10B | 10B |
| jinja2 | 4-5B | <100M | 10B | 10B |
| mammoth | ~2B | <100M | 5B | 5B |
| odfpy | 2-4B | <100M | 5B | 5B |
| **Text/Data Processing** |||||
| tabulate | ~1.4B | <100M | 2B (default) | 5B |
| markdown | ~1.8B | <100M | 2B (default) | 5B |
| python-dateutil | ~1.6B | <100M | 2B (default) | 5B |
| **Utilities** |||||
| attrs | ~1B | <100M | 2B (default) | 2B (default) |
| certifi | ~0.5B | <100M | 2B (default) | 2B (default) |
| charset-normalizer | ~1B | <100M | 2B (default) | 2B (default) |
| **Standard Library** |||||
| json, csv, re | <500M | <100M | 2B (default) | 2B (default) |
| pathlib, os | <500M | <100M | 2B (default) | 2B (default) |
| datetime, time | <500M | <100M | 2B (default) | 2B (default) |

**Key Insights:**
- 🔴 **Heavy packages** (openpyxl, PyPDF2, jinja2): Require 10B fuel for first import
- 🟡 **Medium packages** (tabulate, markdown, dateutil): Work with default 2B but 5B recommended
- 🟢 **Light packages**: All work fine with default 2B budget
- ⚡ **Import caching**: Subsequent imports use cached modules (100x faster, <100M fuel)
- 💡 **Session benefit**: Create session to cache imports permanently across executions

#### MCP Tool Usage Patterns

When using the MCP `execute_code` tool, fuel requirements vary by use case:

| Use Case | Example Code | Fuel Required | Notes |
|----------|-------------|---------------|-------|
| **One-off calculation** | `print(2 + 2)` | <100M | Use default session |
| **File processing (small)** | `data = open('/app/file.txt').read()` | <500M | Use default session |
| **Heavy package import** | `import openpyxl; wb = Workbook()` | 5-7B | Create session with 10B budget |
| **Cached import (session)** | `import openpyxl` (2nd+ time) | <100M | Reuse existing session |
| **Multi-step workflow** | Multiple imports + processing | Variable | Create session, sum individual costs |
| **Data transformation (1K rows)** | CSV parsing + filtering | 500M-1B | Default OK |
| **Data transformation (10K+ rows)** | Large dataset processing | 2-5B | Use 5-10B budget |

**Decision Matrix:**

```
Will you import openpyxl, PyPDF2, or jinja2?
  ├─ YES → Create session with 10B budget
  └─ NO → Will you import tabulate, markdown, dateutil?
          ├─ YES → Create session with 5B budget (recommended)
          └─ NO → Use default session (2B budget)

Will you process large datasets (>10K rows)?
  ├─ YES → Create session with 10B budget
  └─ NO → Use default session

Will you run multiple related executions?
  ├─ YES → Create session (import caching saves 100x fuel!)
  └─ NO → Use default session
```

### Fuel Budget Benchmarks

Based on testing with default 2B fuel budget:

| Operation Category | Example | Fuel Cost | % of 2B Budget |
|-------------------|---------|-----------|----------------|
| **File Operations** | ||||
| `find()` 100 files | `find("*.py", "/app")` | ~5M | 0.25% |
| `tree()` 500 dirs | `tree("/app")` | ~10M | 0.5% |
| `copy_tree()` 100 files | `copy_tree("/app/src", "/app/dst")` | ~15M | 0.75% |
| **Text Processing** | ||||
| `grep()` 1MB text | `grep(r"ERROR", files)` | ~20M | 1% |
| `wc()` 1MB file | `wc("/app/large.txt")` | ~25M | 1.25% |
| `head()` 10 lines | `head("/app/file.txt")` | ~1M | 0.05% |
| **Data Operations** | ||||
| `csv_to_json()` 10K rows | `csv_to_json("/app/data.csv")` | ~50M | 2.5% |
| `group_by()` 10K items | `group_by(data, key_func)` | ~10M | 0.5% |
| `sort_by()` 10K items | `sort_by(data, key_func)` | ~15M | 0.75% |
| **Package Imports** | ||||
| `import json` (stdlib) | First import in session | ~0.5M | 0.025% |
| `import tabulate` | First import | ~1.4B | 70% |
| `import openpyxl` | First import | ~3-5B | 150-250% ⚠️ |
| `import jinja2` | First import | ~4B | 200% ⚠️ |
| `import PyPDF2` | First import | ~3B | 150% ⚠️ |

### Recommendations

**Default Budget (2B instructions)**:
- ✅ Most `sandbox_utils` operations
- ✅ Lightweight packages: tabulate, markdown, python-dateutil, attrs
- ✅ Multiple small operations in one execution
- ❌ First import of openpyxl, jinja2, or PyPDF2

**High Budget (5B instructions)**:
```python
from sandbox import create_sandbox, ExecutionPolicy, RuntimeType

policy = ExecutionPolicy(fuel_budget=5_000_000_000)
sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
```
- ✅ Document processing packages (openpyxl, PyPDF2, jinja2)
- ✅ Complex workflows with multiple operations
- ✅ Large data transformations

**Session Reuse**:
Cached imports in the same session consume minimal fuel:
```python
# First execution: ~4B fuel
result1 = sandbox.execute("import jinja2; print('Loaded')")

# Second execution (same session): ~100M fuel
result2 = sandbox.execute("import jinja2; print('Cached!')")
```

**Optimization Tips**:
1. **Batch operations**: Execute multiple operations in one code block to amortize import costs
2. **Use sessions**: Reuse session ID for related executions to benefit from cached imports
3. **Prefer stdlib**: Standard library modules have negligible import cost
4. **Lazy imports**: Only import heavy packages when needed
5. **Stream large data**: Use `chunk()` and iterators instead of loading entire datasets

---

## Performance Benchmarks

The following benchmarks measure fuel consumption for common `sandbox_utils` operations. These provide guidance for setting appropriate fuel budgets and understanding performance characteristics in the WASM environment.

### Benchmark Results

All benchmarks were run with default policy settings (2B fuel budget, 128MB memory) unless otherwise noted.

#### File Operations (`find()`)

| Scenario | Files | Fuel Consumed | Result |
|----------|-------|---------------|--------|
| Small directory | 10 files | 1.2B instructions | ✓ Success |
| Medium directory | 100 files | 1.6B instructions | ✓ Success |
| Large directory | 1,000 files | >5B instructions | ✗ OutOfFuel (requires 10B+ budget) |

**Recommendation**: For recursive file search across 100+ files, use fuel budget of 3-5B.

#### Text Processing (`grep()`)

| Scenario | Text Size | Fuel Consumed | Result |
|----------|-----------|---------------|--------|
| Small file | 1 KB | 1.2B instructions | ✓ Success |
| Medium file | 1 MB | 2.0B instructions | ✓ Success |
| Large file | 10 MB | 9.7B instructions | ✓ Success (requires 10B+ budget) |

**Recommendation**: Budget ~1B fuel per MB of text for grep operations. For multi-MB files, set fuel to 10-20B.

#### Directory Visualization (`tree()`)

| Scenario | Directories | Fuel Consumed | Result |
|----------|-------------|---------------|--------|
| Small tree | 10 dirs | 1.3B instructions | ✓ Success |
| Medium tree | 100 dirs | 2.2B instructions | ✓ Success |
| Large tree | 500 dirs | 6.2B instructions | ✓ Success (requires 10B budget) |

**Recommendation**: For complex directory trees (100+ directories), use 5-10B fuel budget.

### Performance Guidelines

**General Rules of Thumb**:

1. **Default budget (2B)** is sufficient for:
   - Processing <100 files
   - Text operations on <1MB files
   - Simple data transformations (<1K rows)
   - Most stdlib operations

2. **Medium budget (5B)** recommended for:
   - First-time imports of document packages (Jinja2, Markdown)
   - Processing 100-500 files
   - Text operations on 1-5MB files
   - Data transformations with 1K-10K rows

3. **Large budget (10-20B)** required for:
   - Processing 500+ files recursively
   - Text operations on 10MB+ files
   - Complex data transformations (10K+ rows)
   - Multiple heavy package imports in one execution

**Optimization Strategies**:

- **Filter early**: Use `pattern` and `filter_func` parameters to reduce iteration
- **Limit depth**: Set `max_depth` on `tree()` and `walk()` to constrain recursion
- **Chunk processing**: Use `chunk()` to process large datasets in batches
- **Session reuse**: Cached imports in sessions dramatically reduce fuel for subsequent executions

**Running Benchmarks**:

To run performance benchmarks yourself:

```bash
uv run python benchmark_sandbox_utils.py
```

Results are saved to `benchmark_results_sandbox_utils.json` with detailed metrics for each operation.

---

## Troubleshooting

### Common Issues

**Q: `ModuleNotFoundError` for vendored package**

A: Ensure the sandbox's automatic injection is enabled (default). The sandbox adds `/data/site-packages` to `sys.path` automatically.

**Q: `ImportError` from vendored package**

A: Package may have native dependencies (not WASM-compatible). Check [Package Compatibility Matrix](#package-compatibility-matrix).

**Q: `OutOfFuel` trap with document packages**

A: Increase fuel budget to 5B for first import:
```python
policy = ExecutionPolicy(fuel_budget=5_000_000_000)
```

**Q: `ValueError: Path must be within /app`**

A: All `sandbox_utils` operations enforce `/app` boundary. Use absolute paths within `/app` or relative paths (automatically prefixed with `/app`).

**Q: Package import succeeds but functions fail**

A: Some packages (like urllib3) require networking which is not available in WASI. Only use offline functionality.

---

## See Also

- [README.md](../README.md) - Main project documentation
- [LLM_PROMPT_TEMPLATES.md](LLM_PROMPT_TEMPLATES.md) - Effective prompting patterns
- [WASM_SANDBOX.md](WASM_SANDBOX.md) - Security architecture details
- [ADDING_NEW_RUNTIMES.md](ADDING_NEW_RUNTIMES.md) - Extend to other languages
