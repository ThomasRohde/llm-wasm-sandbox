# JavaScript Vendored Packages

This directory contains pure JavaScript packages that are automatically available in the JavaScript sandbox runtime. These packages are mounted read-only at `/data_js` inside the WASM guest.

## Package Selection Criteria

Vendored packages must meet these requirements:

1. **Pure JavaScript**: No Node.js or browser-specific APIs
2. **Standalone**: No external dependencies
3. **Small size**: Individual packages should be < 50 KB when possible
4. **High utility**: Commonly needed for LLM agent workflows
5. **Well-tested**: Proven implementations with clear APIs

## Available Packages

### CSV Processing

- **csv-simple.js**: Minimal RFC 4180-compliant CSV parser/stringifier
  - Parse CSV strings to arrays of objects
  - Stringify arrays of objects to CSV
  - Handles quoted fields, embedded commas, line breaks
  - Usage: `const csv = requireVendor('csv-simple');`

### JSON Utilities

- **json-utils.js**: JSON path access and schema validation helpers
  - `get(obj, path)`: Safe nested property access (e.g., 'user.address.city')
  - `set(obj, path, value)`: Safe nested property setting
  - `validate(obj, schema)`: Simple JSON schema validation
  - Usage: `const jsonUtils = requireVendor('json-utils');`

### String Utilities

- **string-utils.js**: Common string manipulation functions
  - `slugify(text)`: Convert to URL-friendly slug
  - `truncate(text, length, suffix)`: Truncate with ellipsis
  - `capitalize(text)`: Capitalize first letter
  - `camelCase(text)`, `snakeCase(text)`, `kebabCase(text)`: Case conversion
  - Usage: `const str = requireVendor('string-utils');`

### Sandbox Utilities

- **sandbox-utils.js**: LLM-friendly file and data helpers
  - `readJson(path)`: Read and parse JSON file
  - `writeJson(path, obj)`: Stringify and write JSON file
  - `fileExists(path)`: Check if file exists
  - `readText(path)`: Read text file content
  - `writeText(path, content)`: Write text file
  - Usage: Automatically available via code injection (no require needed)

## Adding New Packages

To add a new vendored package:

1. **Research**: Find a pure JS implementation (no Node.js/browser APIs)
2. **Audit**: Review source code for security issues
3. **Test**: Verify it works in QuickJS WASM environment
4. **Document**: Add entry to this README with API reference
5. **Size check**: Ensure package size is reasonable (< 50 KB preferred)

## Implementation Notes

Packages are loaded via `requireVendor(name)` helper function, which:
1. Reads `/data_js/${name}.js` using QuickJS `std.open()`
2. Executes code with CommonJS-style `module.exports` pattern
3. Returns the exported module

Example:
```javascript
const csv = requireVendor('csv-simple');
const data = csv.parse('name,age\nAlice,30\nBob,25');
console.log(data); // [{name: 'Alice', age: '30'}, {name: 'Bob', age: '25'}]
```

## License

All vendored packages maintain their original licenses. See individual package files for attribution.
