# State Persistence Specification

## ADDED Requirements

### Requirement: JavaScript Auto-Persist Globals
JavaScript runtime SHALL support `auto_persist_globals` flag to automatically save and restore global state across executions using file-backed JSON storage.

#### Scenario: Enable auto-persist globals for JavaScript
- **GIVEN** user creates JavaScript sandbox with `auto_persist_globals=True`
- **WHEN** user executes code that modifies `_state` object
- **THEN** state SHALL be saved to `/app/.session_state.json` after execution
- **AND** next execution SHALL restore `_state` from file automatically

#### Scenario: State persists across multiple JavaScript executions
- **GIVEN** JavaScript sandbox with `auto_persist_globals=True`
- **WHEN** first execution sets `_state.counter = 1`
- **AND** second execution increments `_state.counter += 1`
- **AND** third execution reads `_state.counter`
- **THEN** third execution SHALL see `counter === 3`

#### Scenario: State isolation per session
- **GIVEN** two JavaScript sessions with IDs `session-a` and `session-b`
- **WHEN** both have `auto_persist_globals=True` enabled
- **AND** `session-a` sets `_state.value = 'A'`
- **AND** `session-b` sets `_state.value = 'B'`
- **THEN** each session SHALL maintain independent state files
- **AND** `session-a` SHALL always read `'A'`
- **AND** `session-b` SHALL always read `'B'`

### Requirement: State Wrapping Implementation
The `sandbox.state_js.wrap_stateful_code()` function SHALL inject prologue and epilogue code to handle state save/restore using QuickJS `std` module file I/O APIs.

#### Scenario: Wrapped code includes state load prologue
- **GIVEN** user code is `_state.x = 42;`
- **WHEN** `wrap_stateful_code()` is called
- **THEN** output SHALL start with `import * as std from "std";`
- **AND** output SHALL use `std.open('/app/.session_state.json', 'r')` to open file
- **AND** output SHALL use `FILE.readAsString()` to read JSON content
- **AND** output SHALL parse JSON into `_state` object
- **AND** output SHALL handle missing file gracefully (first execution)

#### Scenario: Wrapped code includes state save epilogue
- **GIVEN** user code modifies `_state` object
- **WHEN** `wrap_stateful_code()` wraps the code
- **THEN** output SHALL use `std.open('/app/.session_state.json', 'w')` to create/overwrite file
- **AND** output SHALL use `FILE.puts(JSON.stringify(_state))` to write JSON
- **AND** output SHALL call `FILE.close()` to flush and close file
- **AND** save SHALL only write JSON-serializable values
- **AND** save SHALL filter out functions and symbols

#### Scenario: State persistence fails gracefully
- **GIVEN** JavaScript execution with `auto_persist_globals=True`
- **WHEN** state file is corrupted (invalid JSON)
- **THEN** execution SHALL start with empty `_state = {}`
- **AND** error SHALL be logged to stderr
- **BUT** execution SHALL NOT crash

### Requirement: State API Equivalence with Python
JavaScript state persistence SHALL mirror Python's `sandbox.state` module behavior where language differences allow.

#### Scenario: _state object mirrors Python globals pattern
- **GIVEN** Python uses `wrap_stateful_code()` to persist top-level variables
- **WHEN** JavaScript uses same function
- **THEN** JavaScript SHALL use `_state` object for persistence
- **AND** syntax difference is documented: `_state.counter = 1` vs `counter = 1`
- **BUT** semantic behavior (multi-turn state) SHALL be identical

#### Scenario: State file format is JSON in both runtimes
- **GIVEN** Python saves state to `.session_state.json`
- **WHEN** JavaScript saves state to same file
- **THEN** both SHALL use standard JSON format
- **AND** both SHALL filter non-serializable types
- **AND** Python SHALL serialize Python primitives (int, str, list, dict, bool, None)
- **AND** JavaScript SHALL serialize JS primitives (number, string, array, object, boolean, null)
