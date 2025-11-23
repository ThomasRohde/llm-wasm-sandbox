# Vendored Package Testing Results

## Summary

Tested 6 new pure-Python packages for WASM compatibility. **5 of 6 packages work successfully** with appropriate fuel budgets.

## Test Results

### ✓ PASS: python-dateutil (1.61B fuel)
- **Status**: Working
- **Fuel consumption**: ~1.6B instructions
- **Dependencies**: Requires `six` package
- **Tested functionality**: Date parsing, relativedelta, timezone handling
- **Notes**: Well within default 2B fuel budget

### ✓ PASS: tabulate (1.36B fuel)
- **Status**: Working  
- **Fuel consumption**: ~1.4B instructions
- **Dependencies**: None (standalone)
- **Tested functionality**: Table formatting (ASCII, Markdown, HTML)
- **Notes**: Lightweight, no dependencies, works great

### ✓ PASS: jinja2 (3.92B fuel)
- **Status**: Working with higher fuel budget
- **Fuel consumption**: ~4B instructions (first import)
- **Dependencies**: Requires `MarkupSafe` package
- **Tested functionality**: Template rendering, HTML escaping
- **Notes**: **Requires 5B fuel budget** for initial import. Subsequent executions in same session use cached imports.

### ✓ PASS: markdown (1.82B fuel)
- **Status**: Working
- **Fuel consumption**: ~1.8B instructions
- **Dependencies**: None (standalone)
- **Tested functionality**: Markdown to HTML conversion
- **Notes**: Close to 2B default limit, but works

### ✗ FAIL: jsonschema
- **Status**: NOT COMPATIBLE
- **Reason**: Requires `rpds-py` which has **native Rust extensions** (`rpds.rpds` compiled module)
- **Alternative**: Use manual JSON validation or simpler validation libraries
- **Recommendation**: **Remove from RECOMMENDED_PACKAGES**

### ✓ PASS: tomli (0.73B fuel)
- **Status**: Working
- **Fuel consumption**: ~730M instructions
- **Dependencies**: None (standalone)
- **Tested functionality**: TOML parsing (Python <3.11 backport)
- **Notes**: Very efficient, well within budget

## Additional Dependencies Installed

To support the new packages, these dependencies were also vendored:

- `six`: Required by python-dateutil (pure-Python)
- `MarkupSafe`: Required by jinja2 (pure-Python)
- `attrs`: Useful standalone library for data classes (pure-Python)

## Fuel Budget Recommendations

| Package | Minimum Fuel | Recommended Fuel | Notes |
|---------|--------------|------------------|-------|
| python-dateutil | 1.7B | 2B (default) | ✓ Works with default |
| tabulate | 1.4B | 2B (default) | ✓ Works with default |
| jinja2 | 4B | 5B | **Requires custom policy** |
| markdown | 1.9B | 2B (default) | ✓ Works with default |
| tomli | 0.8B | 2B (default) | ✓ Works with default |

## Recommendations

1. **Add to RECOMMENDED_PACKAGES**: python-dateutil, tabulate, jinja2, markdown, tomli
2. **Add dependencies**: six, MarkupSafe, attrs
3. **Remove**: jsonschema (incompatible)
4. **Document**: jinja2 requires 5B fuel budget for first import
5. **Update docs**: Note fuel budgets for each package

## Testing Methodology

Each package was tested with:
1. Installation via `scripts/manage_vendor.py`
2. Execution in WASM sandbox with actual code
3. Measurement of fuel consumption
4. Verification of basic functionality

All tests run on:
- Python 3.12 (WASM guest)
- Wasmtime 38.x (host)
- Windows 11 (host OS)
