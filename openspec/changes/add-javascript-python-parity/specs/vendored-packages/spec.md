# Vendored Packages Specification

## ADDED Requirements

### Requirement: JavaScript Vendored Package Library
JavaScript runtime SHALL provide a curated set of pure-JS packages mounted at `/data_js/vendor` for common document processing, text manipulation, and data analysis tasks.

#### Scenario: Core packages available without installation
- **GIVEN** JavaScript sandbox is created
- **WHEN** user imports vendored package via `requireVendor('csv')`
- **THEN** package SHALL be loaded from `/data_js/vendor/csv.js`
- **AND** package SHALL work without npm install
- **AND** package SHALL be pure JavaScript (no native dependencies)

#### Scenario: JavaScript vendor library mirrors Python's package categories
- **GIVEN** Python has vendored packages in categories: document processing, text manipulation, data analysis
- **WHEN** JavaScript vendor library is designed
- **THEN** it SHALL include pure-JS equivalents for key use cases:
  - CSV parsing/writing (like Python's `csv` + vendored tabulate)
  - JSON schema validation (like Python's `jsonschema`)
  - String utilities (like Python's string manipulation)
  - Date/time helpers (like Python's `dateutil`)
- **AND** packages SHALL be selected based on LLM agent usage patterns

#### Scenario: Vendored packages are read-only mounted
- **GIVEN** JavaScript vendor packages exist in `vendor_js/`
- **WHEN** sandbox executes JavaScript code
- **THEN** packages SHALL be mounted at `/data_js/vendor` as read-only
- **AND** all sessions SHALL share the same mount (zero duplication)
- **AND** pattern mirrors Python's `/data/site-packages` mount

### Requirement: requireVendor Helper Function
JavaScript runtime SHALL provide `requireVendor()` helper function (injected automatically) to load vendored packages using CommonJS-like pattern.

#### Scenario: requireVendor loads and executes vendor module
- **GIVEN** vendored package exists at `/data_js/vendor/csv.js`
- **WHEN** user code calls `const csv = requireVendor('csv')`
- **THEN** helper SHALL read file using `std.open()`
- **AND** helper SHALL execute code in isolated scope with `module.exports`
- **AND** helper SHALL return `module.exports` object

#### Scenario: requireVendor handles missing packages gracefully
- **GIVEN** user calls `requireVendor('nonexistent')`
- **WHEN** package file does not exist at `/data_js/vendor/nonexistent.js`
- **THEN** helper SHALL throw descriptive error with package name
- **AND** error SHALL suggest checking available packages

#### Scenario: Automatic injection of requireVendor
- **GIVEN** JavaScript sandbox executes user code
- **WHEN** code does NOT manually import `std` module
- **THEN** runtime SHALL automatically inject prologue with:
  - `import * as std from "std";`
  - `globalThis.requireVendor = function requireVendor(name) { ... }`
- **AND** user code SHALL have immediate access to `requireVendor()`

### Requirement: Vendor Package Selection Criteria
Vendored JavaScript packages SHALL meet strict criteria for security, size, and LLM compatibility.

#### Scenario: Only pure-JS packages allowed
- **GIVEN** a candidate package for vendoring
- **WHEN** package is evaluated for inclusion
- **THEN** package MUST be pure JavaScript (no WASM, no native bindings)
- **AND** package MUST NOT require Node.js-specific APIs (fs, http, child_process)
- **AND** package MUST work in QuickJS environment

#### Scenario: Packages are auditable and reasonably sized
- **GIVEN** a candidate package for vendoring
- **WHEN** package is evaluated
- **THEN** package SHALL be under 100 KB minified (guideline, not hard limit)
- **AND** package source SHALL be auditable (readable, no obfuscation)
- **AND** package SHALL have clear license (MIT, BSD, Apache 2.0 preferred)

#### Scenario: Package documentation includes LLM-friendly examples
- **GIVEN** vendored package is added to `vendor_js/`
- **WHEN** package is documented in `JAVASCRIPT_CAPABILITIES.md`
- **THEN** documentation SHALL include:
  - Import pattern: `const pkg = requireVendor('pkg-name')`
  - Basic usage example (2-5 lines)
  - Common use cases for LLM agents
