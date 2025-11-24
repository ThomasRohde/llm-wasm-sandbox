# Helper Utilities Specification

## ADDED Requirements

### Requirement: JavaScript sandbox_utils Library
JavaScript runtime SHALL provide `sandbox_utils.js` library with LLM-friendly APIs matching the functionality of Python's `sandbox_utils` module.

#### Scenario: sandbox_utils available as vendored package
- **GIVEN** JavaScript sandbox executes user code
- **WHEN** user code calls `const utils = requireVendor('sandbox_utils')`
- **THEN** utils object SHALL be loaded from `/data_js/vendor/sandbox_utils.js`
- **AND** utils SHALL provide file I/O helpers
- **AND** utils SHALL provide JSON convenience functions
- **AND** utils SHALL provide directory listing utilities

#### Scenario: readJson and writeJson helpers
- **GIVEN** user wants to persist data as JSON
- **WHEN** user code calls:
  ```javascript
  const utils = requireVendor('sandbox_utils');
  utils.writeJson('/app/data.json', {key: 'value'});
  const data = utils.readJson('/app/data.json');
  ```
- **THEN** `writeJson()` SHALL use `std.open(path, 'w')` to create file
- **AND** `writeJson()` SHALL use `FILE.puts(JSON.stringify(obj))` to write
- **AND** `readJson()` SHALL use `std.open(path, 'r')` to open file
- **AND** `readJson()` SHALL use `FILE.readAsString()` to read content
- **AND** `readJson()` SHALL parse JSON and return object
- **AND** both SHALL handle errors with descriptive messages

#### Scenario: listFiles helper for directory inspection
- **GIVEN** user needs to list files in `/app` directory
- **WHEN** user code calls:
  ```javascript
  const utils = requireVendor('sandbox_utils');
  const files = utils.listFiles('/app');
  ```
- **THEN** function SHALL use QuickJS `os.readdir(path)` if available
- **AND** function SHALL return array of filenames (strings)
- **AND** function SHALL work recursively if `{recursive: true}` option passed
- **AND** function SHALL mirror Python's `sandbox_utils.list_files()` behavior

### Requirement: API Compatibility with Python sandbox_utils
JavaScript `sandbox_utils.js` SHALL provide JavaScript-idiomatic equivalents of Python `sandbox_utils` functions.

#### Scenario: Function naming follows JavaScript conventions
- **GIVEN** Python has `read_json()` (snake_case)
- **WHEN** JavaScript equivalent is designed
- **THEN** JavaScript SHALL use `readJson()` (camelCase)
- **AND** function signatures SHALL match semantically:
  - Python: `read_json(path: str) -> dict`
  - JavaScript: `readJson(path: string): object`

#### Scenario: Error handling patterns are equivalent
- **GIVEN** Python `sandbox_utils` raises exceptions for file errors
- **WHEN** JavaScript `sandbox_utils` encounters same errors
- **THEN** JavaScript SHALL throw Error objects with descriptive messages
- **AND** error messages SHALL include file path and operation
- **AND** both SHALL handle missing files, permission errors, parse errors

### Requirement: Auto-Injection of Helper Imports
JavaScript runtime SHALL automatically make helper utilities discoverable without manual import configuration.

#### Scenario: Prologue includes std module import
- **GIVEN** JavaScript code needs file I/O or helpers
- **WHEN** sandbox executes code
- **THEN** runtime SHALL inject `import * as std from "std";` at top
- **AND** injection SHALL happen before user code
- **AND** injection SHALL be idempotent (safe if user also imports)

#### Scenario: globalThis.requireVendor available immediately
- **GIVEN** user code wants to load helper library
- **WHEN** code executes without any imports
- **THEN** `requireVendor()` SHALL be available on `globalThis`
- **AND** user can call it directly: `const utils = requireVendor('sandbox_utils')`
- **AND** pattern mirrors Python's automatic sys.path setup
