# JavaScript Capabilities in WASM Sandbox

## Overview

The LLM WASM Sandbox provides a secure JavaScript runtime based on **QuickJS-NG WASI** with:
- **Full ES2020+ support** (arrow functions, destructuring, async/await, classes)
- **QuickJS standard library** (`std` and `os` modules for file I/O)
- **Vendored pure-JS packages** for CSV, JSON, string manipulation
- **`sandbox-utils` library** with file helpers optimized for LLM code generation
- **Session-based state persistence** (automatic global variable saving/restoring)

This document provides a comprehensive reference for all JavaScript capabilities available in the sandbox.

---

## QuickJS Standard Library

QuickJS provides two built-in modules: `std` and `os`. Both are available as **global objects** (no import needed) when running in the sandbox.

### `std` Module - Core I/O and Utilities

The `std` module provides file I/O, process control, and basic utilities.

#### File Operations

##### `std.open(filename, flags, errorObj?)` → `FILE | null`
Open a file and return a FILE object.

**Parameters:**
- `filename` (string): Path to file (must be within `/app`)
- `flags` (string): Open mode:
  - `'r'` - Read mode (file must exist)
  - `'w'` - Write mode (truncate if exists, create if not)
  - `'a'` - Append mode (create if not exists)
  - `'r+'` - Read/write mode (file must exist)
  - `'w+'` - Read/write mode (truncate if exists, create if not)
  - `'a+'` - Read/append mode (create if not exists)
- `errorObj` (object, optional): Object to receive error info

**Returns:** `FILE` object or `null` on error

**Example:**
```javascript
// Read a file
const f = std.open('/app/data.txt', 'r');
if (f) {
    const content = f.readAsString();
    f.close();
    console.log(content);
}

// Write a file
const f2 = std.open('/app/output.txt', 'w');
f2.puts('Hello, World!');
f2.close();

// Error handling
const err = {};
const f3 = std.open('/app/missing.txt', 'r', err);
if (!f3) {
    console.log('Error:', err.message);
}
```

##### FILE Object Methods

**`file.readAsString(max_size?)` → `string`**
Read entire file content as a string.

```javascript
const f = std.open('/app/data.txt', 'r');
const content = f.readAsString();
f.close();
```

**`file.read(buffer, position, length)` → `number`**
Read bytes into a buffer (ArrayBuffer or Uint8Array).

```javascript
const buf = new Uint8Array(1024);
const bytesRead = f.read(buf.buffer, 0, 1024);
```

**`file.write(buffer, position, length)` → `number`**
Write bytes from a buffer.

```javascript
const data = new TextEncoder().encode('Hello');
f.write(data.buffer, 0, data.length);
```

**`file.getline()` → `string | null`**
Read a single line (up to newline). Returns `null` at EOF.

```javascript
const f = std.open('/app/data.txt', 'r');
let line;
while ((line = f.getline()) !== null) {
    console.log(line);
}
f.close();
```

**`file.puts(str)` → `void`**
Write a string to the file.

```javascript
f.puts('First line\n');
f.puts('Second line\n');
```

**`file.printf(format, ...args)` → `void`**
Write formatted output (similar to C printf).

```javascript
f.printf('Name: %s, Age: %d\n', 'Alice', 30);
```

**`file.flush()` → `void`**
Flush buffered output to disk.

```javascript
f.puts('Important data');
f.flush();  // Ensure written immediately
```

**`file.seek(offset, whence)` → `number`**
Move file position. Returns new position.

**Whence values:**
- `std.SEEK_SET` (0) - From beginning of file
- `std.SEEK_CUR` (1) - From current position
- `std.SEEK_END` (2) - From end of file

```javascript
f.seek(0, std.SEEK_SET);  // Rewind to beginning
f.seek(10, std.SEEK_CUR); // Skip 10 bytes forward
f.seek(-5, std.SEEK_END); // 5 bytes before end
```

**`file.tell()` → `number`**
Get current file position.

```javascript
const pos = f.tell();
console.log('Current position:', pos);
```

**`file.eof()` → `boolean`**
Check if at end of file.

```javascript
while (!f.eof()) {
    const line = f.getline();
    console.log(line);
}
```

**`file.close()` → `void`**
Close the file. Always call this to release resources.

```javascript
const f = std.open('/app/data.txt', 'r');
try {
    const content = f.readAsString();
    console.log(content);
} finally {
    f.close();
}
```

#### Process and Environment

##### `std.exit(code)` → never
Exit the JavaScript process with the given exit code.

```javascript
if (invalidInput) {
    console.log('Invalid input');
    std.exit(1);
}
```

##### `std.getenv(name)` → `string | undefined`
Get environment variable value.

```javascript
const apiKey = std.getenv('API_KEY');
if (!apiKey) {
    console.log('API_KEY not set');
}
```

##### `std.setenv(name, value)` → `void`
Set environment variable (process scope only).

```javascript
std.setenv('DEBUG', 'true');
```

##### `std.unsetenv(name)` → `void`
Remove environment variable.

```javascript
std.unsetenv('TEMP_VAR');
```

#### Standard I/O

##### `std.in`, `std.out`, `std.err` - FILE objects
Standard input, output, and error streams.

```javascript
std.out.puts('This goes to stdout\n');
std.err.puts('This goes to stderr\n');
```

#### Utilities

##### `std.gc()` → `void`
Trigger garbage collection (for memory management).

```javascript
// After processing large data
processLargeDataset();
std.gc();  // Free memory
```

##### `std.evalScript(code, options?)` → `any`
Evaluate JavaScript code string.

```javascript
const result = std.evalScript('2 + 2');
console.log(result);  // 4
```

---

### `os` Module - Operating System Interface

The `os` module provides filesystem operations, process management, and system utilities.

#### File System Operations

##### `os.remove(path)` → `number`
Delete a file. Returns 0 on success, -1 on error.

```javascript
const result = os.remove('/app/temp.txt');
if (result === 0) {
    console.log('File deleted');
}
```

##### `os.rename(oldPath, newPath)` → `number`
Rename or move a file. Returns 0 on success.

```javascript
os.rename('/app/old.txt', '/app/new.txt');
```

##### `os.stat(path)` → `[object, error]`
Get file metadata. Returns `[statObject, 0]` on success or `[null, errno]` on error.

**Stat object properties:**
- `dev` - Device ID
- `ino` - Inode number
- `mode` - File mode/permissions
- `nlink` - Number of hard links
- `uid` - User ID
- `gid` - Group ID
- `rdev` - Device ID (if special file)
- `size` - File size in bytes
- `blocks` - Number of 512-byte blocks
- `atime` - Last access time (ms since epoch)
- `mtime` - Last modification time (ms since epoch)
- `ctime` - Last status change time (ms since epoch)

```javascript
const [stat, err] = os.stat('/app/data.txt');
if (err === 0) {
    console.log('File size:', stat.size, 'bytes');
    console.log('Modified:', new Date(stat.mtime));
}
```

##### `os.lstat(path)` → `[object, error]`
Like `os.stat()`, but doesn't follow symbolic links.

##### `os.readdir(path)` → `[array, error]`
List directory contents. Returns `[filenames, 0]` on success.

```javascript
const [files, err] = os.readdir('/app');
if (err === 0) {
    files.forEach(name => console.log(name));
}
```

##### `os.mkdir(path, mode?)` → `number`
Create a directory. Returns 0 on success.

```javascript
os.mkdir('/app/data');
os.mkdir('/app/logs', 0o755);  // With permissions
```

##### `os.rmdir(path)` → `number`
Remove an empty directory. Returns 0 on success.

```javascript
os.rmdir('/app/temp');
```

##### `os.realpath(path)` → `[string, error]`
Resolve absolute path. Returns `[path, 0]` on success.

```javascript
const [absPath, err] = os.realpath('data.txt');
if (err === 0) {
    console.log('Absolute path:', absPath);
}
```

##### `os.getcwd()` → `[string, error]`
Get current working directory.

```javascript
const [cwd, err] = os.getcwd();
console.log('Current directory:', cwd);
```

##### `os.chdir(path)` → `number`
Change current working directory. Returns 0 on success.

```javascript
os.chdir('/app/data');
```

##### `os.symlink(target, linkPath)` → `number`
Create symbolic link. Returns 0 on success.

```javascript
os.symlink('/app/data.txt', '/app/link.txt');
```

##### `os.readlink(path)` → `[string, error]`
Read symbolic link target.

```javascript
const [target, err] = os.readlink('/app/link.txt');
console.log('Link points to:', target);
```

#### Process Management

##### `os.exec(args, options?)` → `number`
Execute a program (replaces current process).

**Note:** Not available in WASI sandbox due to security restrictions.

##### `os.waitpid(pid, options?)` → `[pid, status]`
Wait for child process (not available in WASI).

##### `os.pipe()` → `[array, error]`
Create a pipe (not available in WASI).

#### Timing

##### `os.now()` → `number`
Get current time in milliseconds since Unix epoch.

```javascript
const start = os.now();
// ... do work ...
const elapsed = os.now() - start;
console.log('Elapsed:', elapsed, 'ms');
```

##### `os.sleep(ms)` → `void`
Sleep for specified milliseconds.

**⚠️ Warning:** Sleep consumes fuel but cannot be interrupted by fuel exhaustion during the sleep itself.

```javascript
console.log('Waiting...');
os.sleep(1000);  // Sleep 1 second
console.log('Done!');
```

#### Platform Information

##### `os.platform` → `string`
Platform identifier (e.g., `'linux'`, `'darwin'`, `'win32'`).

```javascript
console.log('Running on:', os.platform);
```

---

## Vendored JavaScript Packages

All vendored packages are located in `/data_js` and can be loaded using the `requireVendor()` helper.

### Loading Packages

```javascript
// Load a vendored package
const csv = requireVendor('csv-simple');
const jsonUtils = requireVendor('json-utils');
const str = requireVendor('string-utils');
```

### CSV Processing (`csv-simple.js`)

RFC 4180-compliant CSV parser and stringifier.

#### `csv.parse(csvString, options?)` → `Array<Object>`
Parse CSV string to array of objects.

**Options:**
- `header` (boolean): First row is header (default: `true`)
- `separator` (string): Field separator (default: `','`)
- `skipEmptyLines` (boolean): Skip blank lines (default: `true`)

**Example:**
```javascript
const csv = requireVendor('csv-simple');

const data = csv.parse(`name,age,city
Alice,30,NYC
Bob,25,LA
Charlie,35,Chicago`);

console.log(data);
// [
//   { name: 'Alice', age: '30', city: 'NYC' },
//   { name: 'Bob', age: '25', city: 'LA' },
//   { name: 'Charlie', age: '35', city: 'Chicago' }
// ]
```

#### `csv.stringify(objects, options?)` → `string`
Convert array of objects to CSV string.

**Options:**
- `header` (boolean): Include header row (default: `true`)
- `separator` (string): Field separator (default: `','`)

**Example:**
```javascript
const data = [
    { name: 'Alice', age: 30 },
    { name: 'Bob', age: 25 }
];

const csvString = csv.stringify(data);
console.log(csvString);
// name,age
// Alice,30
// Bob,25
```

**Handles edge cases:**
- Quoted fields with embedded commas: `"Smith, John"`
- Escaped quotes: `"He said ""Hello"""`
- Embedded newlines in quoted fields
- UTF-8 content

---

### JSON Utilities (`json-utils.js`)

Helper functions for JSON path access and validation.

#### `jsonUtils.get(obj, path, defaultValue?)` → `any`
Safe nested property access using dot notation.

**Example:**
```javascript
const jsonUtils = requireVendor('json-utils');

const user = {
    name: 'Alice',
    address: {
        city: 'NYC',
        zip: '10001'
    }
};

const city = jsonUtils.get(user, 'address.city');
console.log(city);  // 'NYC'

const missing = jsonUtils.get(user, 'address.country', 'USA');
console.log(missing);  // 'USA' (default)
```

#### `jsonUtils.set(obj, path, value)` → `void`
Safe nested property setting using dot notation.

**Example:**
```javascript
const obj = {};
jsonUtils.set(obj, 'user.address.city', 'NYC');
console.log(obj);
// { user: { address: { city: 'NYC' } } }
```

#### `jsonUtils.has(obj, path)` → `boolean`
Check if nested property exists.

```javascript
const exists = jsonUtils.has(user, 'address.city');
console.log(exists);  // true
```

#### `jsonUtils.validate(obj, schema)` → `{ valid: boolean, errors: string[] }`
Simple JSON schema validation.

**Supported schema properties:**
- `type` - 'string', 'number', 'boolean', 'object', 'array', 'null'
- `required` - Array of required property names (for objects)
- `properties` - Object schema for object properties
- `items` - Schema for array items

**Example:**
```javascript
const schema = {
    type: 'object',
    required: ['name', 'age'],
    properties: {
        name: { type: 'string' },
        age: { type: 'number' },
        email: { type: 'string' }
    }
};

const data = { name: 'Alice', age: 30 };
const result = jsonUtils.validate(data, schema);

if (result.valid) {
    console.log('Valid!');
} else {
    console.log('Errors:', result.errors);
}
```

---

### String Utilities (`string-utils.js`)

Common string manipulation functions.

#### `str.slugify(text)` → `string`
Convert text to URL-friendly slug.

```javascript
const str = requireVendor('string-utils');

console.log(str.slugify('Hello World!'));  // 'hello-world'
console.log(str.slugify('Café Paris'));    // 'cafe-paris'
```

#### `str.truncate(text, length, suffix?)` → `string`
Truncate text to specified length.

```javascript
const long = 'This is a very long sentence';
console.log(str.truncate(long, 20));           // 'This is a very lo...'
console.log(str.truncate(long, 20, '…'));      // 'This is a very lo…'
```

#### `str.capitalize(text)` → `string`
Capitalize first letter.

```javascript
console.log(str.capitalize('hello world'));  // 'Hello world'
```

#### `str.camelCase(text)` → `string`
Convert to camelCase.

```javascript
console.log(str.camelCase('hello world'));      // 'helloWorld'
console.log(str.camelCase('user-first-name'));  // 'userFirstName'
```

#### `str.snakeCase(text)` → `string`
Convert to snake_case.

```javascript
console.log(str.snakeCase('helloWorld'));       // 'hello_world'
console.log(str.snakeCase('UserFirstName'));    // 'user_first_name'
```

#### `str.kebabCase(text)` → `string`
Convert to kebab-case.

```javascript
console.log(str.kebabCase('helloWorld'));       // 'hello-world'
console.log(str.kebabCase('UserFirstName'));    // 'user-first-name'
```

#### `str.upperFirst(text)` → `string`
Uppercase first character.

```javascript
console.log(str.upperFirst('hello'));  // 'Hello'
```

#### `str.lowerFirst(text)` → `string`
Lowercase first character.

```javascript
console.log(str.lowerFirst('Hello'));  // 'hello'
```

#### `str.words(text)` → `string[]`
Split text into words.

```javascript
console.log(str.words('hello-world_foo bar'));
// ['hello', 'world', 'foo', 'bar']
```

#### `str.pad(text, length, chars?)` → `string`
Pad string to length (centered).

```javascript
console.log(str.pad('Hi', 6));        // '  Hi  '
console.log(str.pad('Hi', 6, '_'));   // '__Hi__'
```

#### `str.padStart(text, length, chars?)` → `string`
Pad string at start.

```javascript
console.log(str.padStart('5', 3, '0'));  // '005'
```

#### `str.padEnd(text, length, chars?)` → `string`
Pad string at end.

```javascript
console.log(str.padEnd('5', 3, '0'));  // '500'
```

---

## Sandbox Utilities Library

The `sandbox-utils.js` package provides LLM-friendly file and data manipulation helpers. These are **automatically injected** into the global scope, so no `requireVendor()` call is needed.

### File Operations

#### `readJson(path)` → `object`
Read and parse JSON file.

**Example:**
```javascript
// Automatically available (no require needed)
const config = readJson('/app/config.json');
console.log(config.apiKey);
```

**Error handling:**
```javascript
try {
    const data = readJson('/app/missing.json');
} catch (e) {
    console.log('Error:', e.message);
}
```

#### `writeJson(path, obj, indent?)` → `void`
Stringify and write JSON file.

**Parameters:**
- `path` - File path within `/app`
- `obj` - Object to serialize
- `indent` - Number of spaces for indentation (default: 2)

**Example:**
```javascript
const data = {
    users: ['Alice', 'Bob'],
    count: 2
};

writeJson('/app/data.json', data);
writeJson('/app/pretty.json', data, 4);  // 4-space indent
```

#### `readText(path)` → `string`
Read text file content.

```javascript
const content = readText('/app/notes.txt');
console.log(content);
```

#### `writeText(path, content)` → `void`
Write text file.

```javascript
writeText('/app/log.txt', 'Application started\n');
```

#### `appendText(path, content)` → `void`
Append text to file.

```javascript
appendText('/app/log.txt', 'New log entry\n');
appendText('/app/log.txt', 'Another entry\n');
```

#### `fileExists(path)` → `boolean`
Check if file exists.

```javascript
if (fileExists('/app/config.json')) {
    const config = readJson('/app/config.json');
} else {
    console.log('Config not found');
}
```

#### `fileSize(path)` → `number`
Get file size in bytes.

```javascript
const size = fileSize('/app/data.json');
console.log(`File size: ${size} bytes`);
```

#### `readLines(path)` → `string[]`
Read file as array of lines.

```javascript
const lines = readLines('/app/data.txt');
lines.forEach((line, i) => {
    console.log(`Line ${i + 1}: ${line}`);
});
```

#### `writeLines(path, lines)` → `void`
Write array of strings as lines.

```javascript
const lines = ['First line', 'Second line', 'Third line'];
writeLines('/app/output.txt', lines);
```

#### `listFiles(path)` → `string[]`
List files in directory.

```javascript
const files = listFiles('/app');
console.log('Files:', files.join(', '));

// List subdirectory
const dataFiles = listFiles('/app/data');
```

#### `copyFile(src, dest)` → `void`
Copy file to new location.

```javascript
copyFile('/app/data.json', '/app/backup/data.json');
```

#### `removeFile(path)` → `boolean`
Delete file. Returns `true` if successful.

```javascript
const deleted = removeFile('/app/temp.txt');
if (deleted) {
    console.log('File deleted');
}
```

---

## State Persistence

JavaScript sessions support **automatic state persistence** using the `auto_persist_globals` flag. This allows variables to persist across multiple executions in the same session.

### How It Works

1. **Before execution**: Sandbox reads `/app/.session_state.json` and restores previous state
2. **User code executes**: Can read/write to `_state` object
3. **After execution**: Sandbox saves `_state` object back to JSON file

### Usage

**Python side:**
```python
from sandbox import create_sandbox, RuntimeType

# Create session with state persistence
sandbox = create_sandbox(
    runtime=RuntimeType.JAVASCRIPT,
    auto_persist_globals=True
)

# First execution
result1 = sandbox.execute("""
_state.counter = (_state.counter || 0) + 1;
_state.user = 'Alice';
console.log('Counter:', _state.counter);
""")
# Output: Counter: 1

# Second execution (same session)
result2 = sandbox.execute("""
_state.counter = (_state.counter || 0) + 1;
console.log('Counter:', _state.counter);
console.log('User:', _state.user);
""")
# Output: Counter: 2
#         User: Alice
```

### State Object (`_state`)

The `_state` global object is automatically managed:

**Properties:**
- Persists across executions in the same session
- Serialized to JSON (must be JSON-compatible types)
- Automatically initialized as empty object `{}`

**Supported types:**
- ✅ Primitives: `string`, `number`, `boolean`, `null`
- ✅ Arrays: `[1, 2, 3]`
- ✅ Plain objects: `{ key: 'value' }`
- ❌ Functions (not serializable)
- ❌ Symbols (not serializable)
- ❌ `undefined` (becomes `null` in JSON)

**Example patterns:**
```javascript
// Counter pattern
_state.visits = (_state.visits || 0) + 1;

// Accumulator pattern
_state.logs = _state.logs || [];
_state.logs.push(`Event at ${Date.now()}`);

// Configuration pattern
_state.config = _state.config || {
    mode: 'development',
    debug: true
};

// Data collection pattern
_state.users = _state.users || {};
_state.users['alice'] = { age: 30, role: 'admin' };
```

### State File Location

State is stored at `/app/.session_state.json` in the session workspace:

```json
{
  "counter": 5,
  "user": "Alice",
  "logs": ["Event 1", "Event 2"],
  "config": {
    "mode": "production",
    "debug": false
  }
}
```

### Error Handling

If state file is corrupted (invalid JSON), the sandbox:
1. Logs error to stderr
2. Initializes empty `_state = {}`
3. Continues execution (does not crash)

**Resilient pattern:**
```javascript
// Always check and initialize
_state.data = _state.data || [];

// Validate before use
if (Array.isArray(_state.data)) {
    _state.data.push('new item');
} else {
    console.log('State corrupted, reinitializing');
    _state.data = [];
}
```

---

## Common LLM Code Patterns

### Pattern 1: Data Processing Workflow

```javascript
// Read CSV data
const csv = requireVendor('csv-simple');
const rawData = readText('/app/sales.csv');
const sales = csv.parse(rawData);

// Process data
const totalRevenue = sales.reduce((sum, row) => {
    return sum + parseFloat(row.amount);
}, 0);

const topSales = sales
    .sort((a, b) => parseFloat(b.amount) - parseFloat(a.amount))
    .slice(0, 10);

// Write results
writeJson('/app/summary.json', {
    total: totalRevenue,
    count: sales.length,
    average: totalRevenue / sales.length,
    topSales: topSales
});

console.log(`Processed ${sales.length} sales records`);
console.log(`Total revenue: $${totalRevenue.toFixed(2)}`);
```

### Pattern 2: File System Navigation

```javascript
// List all JSON files
const files = listFiles('/app');
const jsonFiles = files.filter(f => f.endsWith('.json'));

console.log(`Found ${jsonFiles.length} JSON files`);

// Process each file
jsonFiles.forEach(filename => {
    const path = `/app/${filename}`;
    const data = readJson(path);
    
    console.log(`${filename}: ${Object.keys(data).length} keys`);
    
    // Analyze data
    const size = fileSize(path);
    console.log(`  Size: ${size} bytes`);
});
```

### Pattern 3: Text Processing

```javascript
// Read input file
const lines = readLines('/app/input.txt');

// Process each line
const str = requireVendor('string-utils');
const processed = lines.map(line => {
    // Clean and normalize
    const clean = line.trim();
    const slug = str.slugify(clean);
    
    return {
        original: clean,
        slug: slug,
        words: str.words(clean).length
    };
});

// Write results
writeJson('/app/processed.json', processed);

// Summary
const totalWords = processed.reduce((sum, p) => sum + p.words, 0);
console.log(`Processed ${processed.length} lines`);
console.log(`Total words: ${totalWords}`);
```

### Pattern 4: Stateful Session Workflow

```javascript
// Initialize state on first run
_state.processed = _state.processed || [];
_state.errors = _state.errors || [];

// Read new data
const files = listFiles('/app/inbox');
const newFiles = files.filter(f => !_state.processed.includes(f));

console.log(`New files to process: ${newFiles.length}`);

// Process each file
newFiles.forEach(filename => {
    try {
        const data = readJson(`/app/inbox/${filename}`);
        
        // Validate
        const jsonUtils = requireVendor('json-utils');
        const result = jsonUtils.validate(data, {
            type: 'object',
            required: ['id', 'name']
        });
        
        if (result.valid) {
            // Process valid data
            writeJson(`/app/processed/${filename}`, data);
            _state.processed.push(filename);
            console.log(`✓ Processed: ${filename}`);
        } else {
            _state.errors.push({ file: filename, errors: result.errors });
            console.log(`✗ Invalid: ${filename}`);
        }
    } catch (e) {
        _state.errors.push({ file: filename, error: e.message });
        console.log(`✗ Error: ${filename} - ${e.message}`);
    }
});

// Save state summary
writeJson('/app/state.json', {
    processed: _state.processed.length,
    errors: _state.errors.length
});
```

### Pattern 5: Report Generation

```javascript
// Collect data from multiple sources
const sales = readJson('/app/data/sales.json');
const customers = readJson('/app/data/customers.json');
const products = readJson('/app/data/products.json');

// Calculate metrics
const totalSales = sales.reduce((sum, s) => sum + s.amount, 0);
const avgSale = totalSales / sales.length;

const topCustomers = customers
    .map(c => ({
        ...c,
        spent: sales
            .filter(s => s.customerId === c.id)
            .reduce((sum, s) => sum + s.amount, 0)
    }))
    .sort((a, b) => b.spent - a.spent)
    .slice(0, 5);

// Generate report
const report = `
# Sales Report

## Overview
- Total Sales: $${totalSales.toFixed(2)}
- Average Sale: $${avgSale.toFixed(2)}
- Total Customers: ${customers.length}
- Total Products: ${products.length}

## Top 5 Customers
${topCustomers.map((c, i) => 
    `${i + 1}. ${c.name} - $${c.spent.toFixed(2)}`
).join('\n')}

Generated: ${new Date().toISOString()}
`;

writeText('/app/report.md', report);
console.log('Report generated successfully');
```

### Pattern 6: Data Transformation Pipeline

```javascript
// Pipeline: CSV → JSON → filtered → summary

// Step 1: Parse CSV
const csv = requireVendor('csv-simple');
const rawCsv = readText('/app/input.csv');
const records = csv.parse(rawCsv);

console.log(`Step 1: Parsed ${records.length} records`);

// Step 2: Transform and validate
const jsonUtils = requireVendor('json-utils');
const transformed = records.map(record => ({
    id: parseInt(record.id),
    name: record.name,
    score: parseFloat(record.score),
    status: record.status
}));

// Step 3: Filter
const filtered = transformed.filter(r => r.score >= 80);
console.log(`Step 2: Filtered to ${filtered.length} records (score >= 80)`);

// Step 4: Generate summary
const summary = {
    total: records.length,
    filtered: filtered.length,
    avgScore: filtered.reduce((sum, r) => sum + r.score, 0) / filtered.length,
    maxScore: Math.max(...filtered.map(r => r.score)),
    minScore: Math.min(...filtered.map(r => r.score))
};

// Save outputs
writeJson('/app/filtered.json', filtered);
writeJson('/app/summary.json', summary);

console.log('Pipeline completed:');
console.log(JSON.stringify(summary, null, 2));
```

---

## Performance Guidelines

### Fuel Budget Benchmarks

Based on testing with default 2B fuel budget:

| Operation Category | Example | Fuel Cost | % of 2B Budget |
|-------------------|---------|-----------|----------------|
| **Basic Operations** | ||||
| Simple computation | Loop 1000×1000 | ~200M | 10% |
| String manipulation | Process 1000 strings | ~50M | 2.5% |
| JSON parse/stringify | 10KB JSON | ~30M | 1.5% |
| **File I/O** | ||||
| Read small file (1KB) | `readText()` | ~20M | 1% |
| Read large file (1MB) | `readText()` | ~200M | 10% |
| Write file | `writeText()` | ~30M | 1.5% |
| List directory (100 files) | `listFiles()` | ~40M | 2% |
| **Vendored Packages** | ||||
| CSV parse (1000 rows) | `csv.parse()` | ~100M | 5% |
| CSV stringify (1000 rows) | `csv.stringify()` | ~80M | 4% |
| String utilities | `slugify()`, `camelCase()` | ~5M | 0.25% |
| JSON path access | `jsonUtils.get()` | ~2M | 0.1% |

### Recommendations

**Default Budget (2B instructions)**:
- ✅ Most file operations (<1MB files)
- ✅ Vendored package usage
- ✅ Data processing (<5K records)
- ✅ Multiple operations in one execution
- ❌ Very large file processing (>10MB)
- ❌ Nested loops with millions of iterations

**High Budget (5B instructions)**:
```python
from sandbox import create_sandbox, ExecutionPolicy, RuntimeType

policy = ExecutionPolicy(fuel_budget=5_000_000_000)
sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, policy=policy)
```
- ✅ Large file processing (1-50MB)
- ✅ Complex data transformations (10K+ records)
- ✅ Multiple vendored package operations
- ✅ Nested computation (within reason)

**Session Reuse Benefits**:
State persistence has minimal overhead:
```javascript
// First execution: ~50M fuel
_state.counter = 1;

// Second execution: ~30M fuel (state loading is fast)
_state.counter++;
```

**Optimization Tips**:
1. **Batch file operations**: Read/write files once rather than repeatedly
2. **Use appropriate data structures**: Arrays for iteration, objects for lookup
3. **Avoid unnecessary computation**: Cache results, use early returns
4. **Leverage native methods**: Use built-in Array methods (map, filter, reduce)
5. **Minimize JSON serialization**: Only stringify when writing to files

---

## QuickJS API Patterns & Common Pitfalls

### Critical Patterns for LLM Code Generation

When generating JavaScript code for the sandbox, follow these patterns to avoid common pitfalls:

#### ✅ Pattern 1: Tuple Returns - Don't Destructure Directly

QuickJS functions often return tuples `[value, error]`. Do NOT destructure these directly.

**❌ WRONG:**
```javascript
// This will fail with "TypeError: value is not iterable"
const [stat, err] = os.stat('/app/file.txt');
```

**✅ RIGHT:**
```javascript
// Call function, check truthiness, then access array elements
const statResult = os.stat('/app/file.txt');
if (statResult && statResult[1] === 0) {
    const stat = statResult[0];
    console.log('File size:', stat.size);
}
```

**Why:** QuickJS tuple returns are actual arrays, but JavaScript destructuring expects iterables. Direct destructuring can fail depending on how the function returns data.

#### ✅ Pattern 2: Always Use /app Prefix for File Paths

All file operations MUST use `/app/` prefix due to WASI capability restrictions.

**❌ WRONG:**
```javascript
const data = readJson('config.json');  // Permission denied!
const f = std.open('data.txt', 'r');   // Permission denied!
```

**✅ RIGHT:**
```javascript
const data = readJson('/app/config.json');  // Works
const f = std.open('/app/data.txt', 'r');   // Works
```

**Why:** WASI sandbox only grants access to `/app` directory. Relative paths fail.

#### ✅ Pattern 3: Check File Existence Before Operations

**❌ WRONG:**
```javascript
// Crashes if file doesn't exist
const data = readJson('/app/config.json');
```

**✅ RIGHT:**
```javascript
if (fileExists('/app/config.json')) {
    const data = readJson('/app/config.json');
    console.log('Config loaded');
} else {
    console.log('Config not found, using defaults');
    const data = { mode: 'default' };
}
```

**Why:** Missing files throw errors. Always validate before reading.

#### ✅ Pattern 4: Initialize State Variables Before Use

When using state persistence (`auto_persist_globals=True`), always initialize.

**❌ WRONG:**
```javascript
// Crashes on first run if _state.counter doesn't exist
_state.counter += 1;
```

**✅ RIGHT:**
```javascript
// Initialize with default if undefined
_state.counter = (_state.counter || 0) + 1;

// OR use explicit check
if (typeof _state.counter === 'undefined') {
    _state.counter = 0;
}
_state.counter += 1;
```

**Why:** `_state` starts as empty object `{}`. Accessing undefined properties fails.

#### ✅ Pattern 5: Use Global Helpers Over std/os Globals

For simple file operations, prefer global helpers (auto-injected) over std/os globals.

**🟡 WORKS BUT VERBOSE:**
```javascript
// std and os are globals (via --std flag), not ES6 modules
const f = std.open('/app/data.json', 'r');
const content = f.readAsString();
f.close();
const data = JSON.parse(content);
```

**✅ BETTER:**
```javascript
// No import needed, auto-injected helper
const data = readJson('/app/data.json');
```

**Why:** Global helpers handle error checking and resource cleanup automatically.

#### ✅ Pattern 6: Error Handling with try/catch

Always wrap file operations in try/catch to handle errors gracefully.

**❌ WRONG:**
```javascript
const data = readJson('/app/data.json');
processData(data);
```

**✅ RIGHT:**
```javascript
try {
    const data = readJson('/app/data.json');
    processData(data);
} catch (e) {
    console.error('Error reading file:', e.message);
    // Fallback behavior
    const data = { default: true };
    processData(data);
}
```

**Why:** File operations can fail (missing file, permission denied, invalid JSON, etc.).

#### ✅ Pattern 7: Vendored Package Loading

Use `requireVendor()` for vendored packages (not Node.js `require()`).

**❌ WRONG:**
```javascript
const csv = require('csv-simple');  // ReferenceError!
```

**✅ RIGHT:**
```javascript
const csv = requireVendor('csv-simple');
const data = csv.parse(csvString);
```

**Why:** Node.js `require()` doesn't exist in QuickJS. Use sandbox-provided `requireVendor()`.

#### ✅ Pattern 8: Array/Object Iteration

Use standard JavaScript iteration, avoid Node.js-specific patterns.

**✅ CORRECT:**
```javascript
// Array iteration
const numbers = [1, 2, 3, 4, 5];
numbers.forEach(n => console.log(n));

// Object iteration
const obj = { a: 1, b: 2, c: 3 };
Object.keys(obj).forEach(key => {
    console.log(key, obj[key]);
});

// Modern array methods work
const doubled = numbers.map(n => n * 2);
const evens = numbers.filter(n => n % 2 === 0);
const sum = numbers.reduce((acc, n) => acc + n, 0);
```

**❌ AVOID:**
```javascript
// Node.js-specific patterns that don't work
for await (const item of asyncIterator) { }  // No async/await in this build
```

**Why:** QuickJS supports ES2020+ standard features but not Node.js-specific APIs.

---

## Security Considerations

### Filesystem Isolation

**What's allowed:**
- ✅ Read/write any file under `/app`
- ✅ Create subdirectories under `/app`
- ✅ List files in `/app`

**What's blocked:**
- ❌ Access files outside `/app` (e.g., `/etc/passwd`)
- ❌ Parent directory traversal (`../..`)
- ❌ Absolute paths outside `/app`
- ❌ Symbolic links pointing outside `/app`

**Enforcement**: WASI capability system blocks all unauthorized access at the OS level.

### Resource Limits

**Fuel (CPU time):**
- Default: 2B instructions
- Exhaustion → Execution terminated with `OutOfFuel` error
- ⚠️ `os.sleep()` consumes fuel but cannot be interrupted during sleep

**Memory:**
- Default: 128MB linear memory
- Exhaustion → Execution fails with memory error
- All allocations are within WASM sandbox (isolated from host)

**Output:**
- Stdout cap: 2MB (configurable)
- Stderr cap: 1MB (configurable)
- Exceeding cap → Output truncated

### No Network Access

**Completely disabled:**
- No HTTP/HTTPS requests
- No socket creation
- No DNS lookups
- No WebSocket connections

This is enforced at the WASI level (no network capabilities granted).

### Environment Variables

**Whitelist pattern:**
Only explicitly allowed environment variables are accessible via `std.getenv()`.

**Python configuration:**
```python
from sandbox import create_sandbox, ExecutionPolicy, RuntimeType

policy = ExecutionPolicy(
    env={"API_KEY": "secret", "MODE": "production"}
)
sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, policy=policy)
```

**JavaScript access:**
```javascript
const apiKey = std.getenv('API_KEY');  // Works
const path = std.getenv('PATH');        // undefined (not whitelisted)
```

---

## Troubleshooting

### Common Issues

**Q: `Error: Vendor package not found: package-name`**

A: The package doesn't exist in `/data_js`. Check available packages:
```javascript
const files = os.readdir('/data_js');
console.log('Available packages:', files[0]);
```

**Q: `Error: Permission denied` when accessing file**

A: File is outside `/app`. All file paths must be within `/app`:
```javascript
// ✓ Correct
const data = readJson('/app/data.json');

// ✗ Wrong
const data = readJson('/etc/passwd');  // Permission denied
```

**Q: `OutOfFuel` trap during execution**

A: Code exceeded fuel budget. Increase budget or optimize code:
```python
# Increase fuel budget
policy = ExecutionPolicy(fuel_budget=5_000_000_000)
sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, policy=policy)
```

**Q: State not persisting across executions**

A: Ensure `auto_persist_globals=True` is set:
```python
sandbox = create_sandbox(
    runtime=RuntimeType.JAVASCRIPT,
    auto_persist_globals=True  # Required!
)
```

**Q: `TypeError: Cannot read property of undefined`**

A: Common with state persistence. Always initialize:
```javascript
// ✓ Always initialize before use
_state.data = _state.data || [];
_state.data.push('item');

// ✗ May fail if state doesn't exist
_state.data.push('item');
```

**Q: Functions not persisting in state**

A: Only JSON-compatible types persist. Functions are not serializable:
```javascript
// ✗ Won't persist
_state.myFunc = () => console.log('Hi');

// ✓ Store data, reconstruct functions
_state.config = { mode: 'fast' };
const processData = _state.config.mode === 'fast' ? fastFunc : slowFunc;
```

---

## Limitations

### QuickJS-Specific

1. **No async/await in this build**: Current QuickJS-NG WASI binary doesn't support promises/async
2. **No module imports**: Cannot use ES6 `import` statements (use `requireVendor()` instead)
3. **Limited file I/O APIs**: Only `std` and `os` modules (no Node.js `fs` module)
4. **No setTimeout/setInterval**: No built-in timer APIs
5. **No npm packages**: Only vendored pure-JS packages

### WASI/Sandbox Constraints

1. **No networking**: Cannot make HTTP requests, connect to databases, etc.
2. **No subprocess execution**: Cannot spawn child processes
3. **No threading**: Single-threaded execution only
4. **Filesystem limited to `/app`**: Cannot access host filesystem
5. **No host function calls**: Cannot call Python functions from JavaScript

### Workarounds

**For async operations**: Use polling patterns with `os.sleep()`
```javascript
let attempts = 0;
while (attempts < 10) {
    if (fileExists('/app/ready.flag')) {
        break;
    }
    os.sleep(100);  // Wait 100ms
    attempts++;
}
```

**For data sharing between languages**: Use JSON files in `/app`
```javascript
// JavaScript writes
writeJson('/app/shared.json', { status: 'done' });

// Python reads (in separate execution)
// result = readJson('/app/shared.json')
```

**For missing npm packages**: Vendor pure-JS implementations
- Add to `vendor_js/` directory
- Load with `requireVendor('package-name')`

---

## See Also

- [README.md](../README.md) - Main project documentation
- [PYTHON_CAPABILITIES.md](PYTHON_CAPABILITIES.md) - Python runtime capabilities
- [MCP_INTEGRATION.md](MCP_INTEGRATION.md) - Model Context Protocol integration
- [FUEL_BUDGETING.md](FUEL_BUDGETING.md) - Fuel budget planning
- [ERROR_GUIDANCE.md](ERROR_GUIDANCE.md) - Error troubleshooting

---

## Version History

- **v0.4.0** (2024-01) - Added state persistence (`auto_persist_globals`)
- **v0.3.0** (2024-01) - Added vendored packages (CSV, JSON utils, string utils)
- **v0.2.0** (2024-01) - Added `sandbox-utils` library
- **v0.1.0** (2024-01) - Initial JavaScript runtime with QuickJS-NG WASI
