# Fuel Budget Planning Guide

Complete reference for understanding, planning, and optimizing fuel budgets in the LLM WASM Sandbox.

## Table of Contents

1. [What is Fuel?](#what-is-fuel)
2. [Default Budgets](#default-budgets)
3. [Package Fuel Requirements](#package-fuel-requirements)
4. [Estimation Strategies](#estimation-strategies)
5. [Fuel Analysis Metadata](#fuel-analysis-metadata)
6. [Optimization Techniques](#optimization-techniques)
7. [Common Scenarios](#common-scenarios)
8. [Troubleshooting](#troubleshooting)

## What is Fuel?

**Fuel** is Wasmtime's deterministic execution limiting mechanism that counts **WASM instructions executed**. When a code execution reaches the fuel budget, it traps immediately with `OutOfFuel` error.

### Key Characteristics

- ✅ **Deterministic**: Same code consumes same fuel across runs
- ✅ **Granular**: Counts individual WASM instructions (~1-10 per Python/JS operation)
- ✅ **Preemptive**: Can interrupt infinite loops and runaway code
- ⚠️ **Not wall-clock time**: Fast CPU ≠ more fuel
- ⚠️ **Cannot interrupt blocking I/O**: Use OS-level timeouts for sleep/network

### Why Fuel Matters

1. **Security**: Prevents denial-of-service from infinite loops
2. **Resource Control**: Predictable computation limits for multi-tenant systems
3. **Cost Management**: Meter LLM-generated code execution
4. **SLA Enforcement**: Guarantee maximum execution bounds

## Default Budgets

### Built-In Defaults

| Configuration | Fuel Budget | Use Case |
|--------------|-------------|----------|
| `ExecutionPolicy` default | 10,000,000,000 (10B) | General-purpose code, light packages |
| MCP Server default | 10,000,000,000 (10B) | Standard MCP tool executions |
| Custom session | User-defined | Heavy packages, complex algorithms |

### Budget Breakdown

```python
# 10B instructions can typically handle:
- ~100 simple calculations
- ~1,000 list operations
- ~10,000 dictionary lookups
- 1-2 heavy package imports (openpyxl, jinja2)
- 50+ light package imports (json, csv, re)
```

## Package Fuel Requirements

### Python Packages

#### Heavy Packages (5B+ fuel)

| Package | First Import | Cached Import | Purpose |
|---------|-------------|---------------|---------|
| **openpyxl** | 5,000,000,000 - 7,000,000,000 | <100,000,000 | Excel .xlsx read/write |
| **jinja2** | 5,000,000,000 - 10,000,000,000 | <100,000,000 | Template engine |
| **PyPDF2** | 5,000,000,000 - 6,000,000,000 | <100,000,000 | PDF manipulation |

**Recommendation:** Use 15-20B budget for code importing any heavy package.

#### Medium Packages (2-5B fuel)

| Package | First Import | Cached Import | Purpose |
|---------|-------------|---------------|---------|
| **tabulate** | 2,000,000,000 - 3,000,000,000 | <50,000,000 | Table formatting |
| **markdown** | 2,000,000,000 - 3,000,000,000 | <50,000,000 | Markdown parsing |
| **python-dateutil** | 2,000,000,000 - 2,500,000,000 | <50,000,000 | Date parsing |

**Recommendation:** Use 10-15B budget (default 10B may be tight).

#### Light Packages (<2B fuel)

| Package | First Import | Cached Import | Purpose |
|---------|-------------|---------------|---------|
| **certifi** | <1,000,000,000 | <10,000,000 | CA certificates |
| **charset-normalizer** | <1,500,000,000 | <20,000,000 | Character encoding |
| **attrs** | <1,000,000,000 | <10,000,000 | Classes without boilerplate |
| **tomli** | <1,000,000,000 | <10,000,000 | TOML parser |

**Recommendation:** Default 10B budget is sufficient.

### JavaScript Packages

JavaScript vendored packages are lightweight - all fit within default 10B budget:

| Package | Fuel Usage | Purpose |
|---------|-----------|---------|
| **csv-simple** | <500,000,000 | CSV parsing/stringification |
| **string-utils** | <300,000,000 | String manipulation |
| **json-utils** | <200,000,000 | JSON operations |
| **sandbox-utils** | <100,000,000 | Helper functions |

**Recommendation:** Default 10B budget is always sufficient for JavaScript.

### Import Caching

**Critical Optimization:** Imports are cached within a session after first execution.

```python
# First execution in session
result1 = sandbox.execute("import openpyxl")
print(result1.fuel_consumed)  # ~7,000,000,000 (7B)

# Second execution in SAME session
result2 = sandbox.execute("import openpyxl")
print(result2.fuel_consumed)  # ~50,000,000 (50M) - 140x faster!
```

**Best Practice:** Use persistent sessions with `auto_persist_globals=True` for workflows importing heavy packages repeatedly.

## Estimation Strategies

### Method 1: Profile with Test Execution

```python
from sandbox import create_sandbox, RuntimeType, ExecutionPolicy

# Start with generous budget for profiling
policy = ExecutionPolicy(fuel_budget=50_000_000_000)  # 50B
sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)

result = sandbox.execute(your_code)
print(f"Actual fuel consumed: {result.fuel_consumed:,}")

# Set production budget with 50-100% margin
recommended_budget = int(result.fuel_consumed * 1.5)
print(f"Recommended budget: {recommended_budget:,}")
```

### Method 2: Use Fuel Analysis Metadata

The sandbox automatically provides fuel analysis in results:

```python
result = sandbox.execute(code)

if 'fuel_analysis' in result.metadata:
    analysis = result.metadata['fuel_analysis']
    print(f"Status: {analysis['status']}")              # efficient/moderate/warning/critical
    print(f"Utilization: {analysis['utilization_percent']:.1f}%")
    print(f"Recommendation: {analysis['recommendation']}")
    print(f"Likely causes: {analysis['likely_causes']}")
```

**Status Thresholds:**
- **efficient** (<50%): Budget is generous, can reduce if desired
- **moderate** (50-75%): Good balance, no action needed
- **warning** (75-90%): Close to limit, increase for similar workloads
- **critical** (90-100%): Very tight, must increase for production use
- **exhausted** (100%): OutOfFuel trap occurred

### Method 3: Sum Package Requirements

```python
# Manual estimation based on packages
packages_in_code = ["openpyxl", "jinja2", "tabulate"]

fuel_requirements = {
    "openpyxl": 7_000_000_000,
    "jinja2": 10_000_000_000,
    "tabulate": 3_000_000_000,
}

total_fuel = sum(fuel_requirements[pkg] for pkg in packages_in_code)
recommended_budget = int(total_fuel * 1.5)  # 50% margin

print(f"Estimated fuel needed: {total_fuel:,}")
print(f"Recommended budget: {recommended_budget:,}")
# Output: Recommended budget: 30,000,000,000 (30B)
```

## Fuel Analysis Metadata

### Structure

```python
result.metadata['fuel_analysis'] = {
    "consumed": 8_500_000_000,           # Instructions executed
    "budget": 10_000_000_000,            # Allocated budget
    "utilization_percent": 85.0,         # Usage percentage
    "status": "warning",                 # Classification
    "recommendation": "...",             # Actionable guidance
    "likely_causes": ["..."],            # Detected patterns
    "suggested_budget": 15_000_000_000   # Concrete recommendation
}
```

### Status Classifications

#### Efficient (<50%)

```python
{
    "status": "efficient",
    "utilization_percent": 35.2,
    "recommendation": "Fuel budget is sufficient with comfortable margin. No changes needed."
}
```

**Action:** None required. Consider reducing budget if optimizing costs.

#### Moderate (50-75%)

```python
{
    "status": "moderate",
    "utilization_percent": 62.8,
    "recommendation": "Fuel utilization is moderate. Current budget is appropriate for this workload."
}
```

**Action:** None required. Good balance between safety margin and efficiency.

#### Warning (75-90%)

```python
{
    "status": "warning",
    "utilization_percent": 83.4,
    "recommendation": "Fuel usage is high (83%). Consider increasing budget to 15-20B for similar workloads to ensure reliability.",
    "suggested_budget": 17_000_000_000
}
```

**Action:** Increase budget for production use to avoid OutOfFuel risks.

#### Critical (90-100%)

```python
{
    "status": "critical",
    "utilization_percent": 96.7,
    "recommendation": "Fuel usage is critical (97%). MUST increase budget to 20B+ for future executions to prevent failures.",
    "suggested_budget": 25_000_000_000,
    "likely_causes": [
        "Heavy package import detected: openpyxl",
        "Complex data processing"
    ]
}
```

**Action:** REQUIRED - increase budget immediately. Current budget is unsafe.

#### Exhausted (OutOfFuel)

```python
{
    "status": "exhausted",
    "utilization_percent": 100.0,
    "recommendation": "Execution exceeded fuel budget. Increase to 20B+ or simplify code.",
    "suggested_budget": 20_000_000_000,
    "likely_causes": [
        "OutOfFuel trap occurred",
        "Heavy package: openpyxl (requires 7B)",
        "Potential infinite loop or complex algorithm"
    ]
}
```

**Action:** CRITICAL - execution failed. Must increase budget or refactor code.

### Interpreting Likely Causes

```python
"likely_causes": [
    "Heavy package import detected: openpyxl",      # High fuel without code complexity
    "Complex data processing",                      # High fuel from algorithm
    "First-time package import",                    # Explain why fuel is high
    "Large dataset processing (1000+ items)"        # Data volume impact
]
```

Use likely_causes to understand **why** fuel was consumed and make informed decisions.

## Optimization Techniques

### 1. Use Persistent Sessions for Heavy Packages

```python
# ❌ BAD: Import heavy package in every execution
for i in range(10):
    result = sandbox.execute(f"""
import sys
sys.path.insert(0, '/data/site-packages')
import openpyxl  # 7B fuel EVERY time
# ... use openpyxl
    """)
# Total fuel: 70B (7B × 10)

# ✅ GOOD: Create persistent session, import once
from sandbox import create_sandbox, RuntimeType, ExecutionPolicy

policy = ExecutionPolicy(fuel_budget=20_000_000_000)  # Higher budget for first import
sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)

# First execution: high fuel
sandbox.execute("""
import sys
sys.path.insert(0, '/data/site-packages')
import openpyxl
""")

# Subsequent executions: cached import, low fuel
for i in range(9):
    result = sandbox.execute("# openpyxl already imported, just use it")
    # Fuel: ~50M each (cached)
# Total fuel: ~7.5B (7B + 0.05B×9) - 10x reduction!
```

### 2. Lazy Import Patterns

```python
# ❌ BAD: Import everything upfront
import sys
sys.path.insert(0, '/data/site-packages')
import openpyxl    # 7B
import jinja2      # 10B
import PyPDF2      # 6B
# Total: 23B just for imports!

# ✅ GOOD: Import only what's needed
if processing_excel:
    import openpyxl
elif processing_pdf:
    import PyPDF2
# Only pay for what you use
```

### 3. Use Lighter Alternatives

| Heavy Package | Light Alternative | Fuel Savings |
|---------------|------------------|--------------|
| openpyxl (7B) | XlsxWriter (3-4B) for write-only | ~3B (40%) |
| jinja2 (10B) | str.format() for simple templates | ~10B (100%) |
| markdown (3B) | Manual string manipulation | ~3B (100%) |

```python
# ❌ BAD: Heavy package for simple task
import jinja2  # 10B fuel
template = jinja2.Template("Hello {{ name }}")
result = template.render(name="World")

# ✅ GOOD: Built-in string formatting
result = "Hello {name}".format(name="World")  # <1M fuel
```

### 4. Algorithmic Optimization

```python
# ❌ BAD: O(n²) complexity
results = []
for i in range(1000):
    for j in range(1000):  # 1M iterations
        results.append(i * j)
# Fuel: ~5-10B

# ✅ GOOD: O(n) complexity
results = [i * j for i in range(1000) for j in range(1000)]  # Same result
# Fuel: ~2-3B (50% reduction via list comprehension optimization)
```

### 5. Chunk Large Datasets

```python
# ❌ BAD: Process all at once
data = load_10000_rows()
results = [complex_transform(row) for row in data]  # May hit fuel limit

# ✅ GOOD: Process in chunks
data = load_10000_rows()
chunk_size = 1000
for i in range(0, len(data), chunk_size):
    chunk = data[i:i+chunk_size]
    chunk_results = sandbox.execute(f"process({chunk})")
    # Each execution stays within budget
```

## Common Scenarios

### Scenario 1: Excel File Processing

**Task:** Read 1000-row Excel file, transform data, write output.

**Fuel Breakdown:**
- openpyxl import (first time): 7B
- Load workbook: 500M
- Iterate rows: 200M
- Transform logic: 1B
- Write output: 500M
- **Total: ~9.2B**

**Recommended Budget:** 15B (9.2B × 1.6 margin)

```python
from sandbox import create_sandbox, RuntimeType, ExecutionPolicy

policy = ExecutionPolicy(fuel_budget=15_000_000_000)
sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)

code = """
import sys
sys.path.insert(0, '/data/site-packages')
import openpyxl

wb = openpyxl.load_workbook('/app/data.xlsx')
ws = wb.active
for row in ws.iter_rows(min_row=2, values_only=True):
    # Process row
    pass
wb.save('/app/output.xlsx')
"""

result = sandbox.execute(code)
print(f"Fuel used: {result.fuel_consumed:,}")
# Check fuel_analysis for optimization opportunities
```

### Scenario 2: Multi-Turn LLM Agent

**Task:** Agent maintains state across 10 conversation turns, occasionally imports packages.

**Fuel Strategy:**
1. Create persistent session with auto_persist_globals
2. Front-load heavy imports in first turn
3. Subsequent turns use cached imports

```python
from sandbox import create_sandbox, RuntimeType, ExecutionPolicy

# Higher budget for first turn (imports)
policy = ExecutionPolicy(fuel_budget=20_000_000_000)
sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)

# Turn 1: Setup imports (high fuel)
turn1 = sandbox.execute("""
import sys
sys.path.insert(0, '/data/site-packages')
import openpyxl
import tabulate
counter = 0
""")
print(f"Turn 1 fuel: {turn1.fuel_consumed:,}")  # ~10B

# Turns 2-10: Use cached imports (low fuel)
for i in range(2, 11):
    turn = sandbox.execute(f"""
counter += 1
# openpyxl and tabulate already available
    """)
    print(f"Turn {i} fuel: {turn.fuel_consumed:,}")  # ~50M each
```

**Total Fuel:** ~10.5B (10B first turn + 0.5B for 9 subsequent turns)  
**Recommended Budget:** 20B for first turn, 2B for subsequent turns

### Scenario 3: PDF Report Generation

**Task:** Generate multi-page PDF report with jinja2 templates and PyPDF2.

**Fuel Breakdown:**
- jinja2 import: 10B
- PyPDF2 import: 6B
- Template rendering: 500M
- PDF creation: 1B
- **Total: ~17.5B**

**Recommended Budget:** 25-30B

```python
policy = ExecutionPolicy(fuel_budget=30_000_000_000)
sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)

# This requires both heavy packages
result = sandbox.execute("""
import sys
sys.path.insert(0, '/data/site-packages')
import jinja2
import PyPDF2
# Generate report...
""")
```

### Scenario 4: JavaScript CSV Processing

**Task:** Parse CSV, transform data, write JSON output.

**Fuel Breakdown:**
- csv-simple require: 300M
- Parse 1000 rows: 200M
- Transform: 500M
- JSON stringify: 100M
- Write file: 50M
- **Total: ~1.15B**

**Recommended Budget:** Default 10B is more than sufficient

```javascript
const csv = requireVendor('csv-simple')
const data = readText('/app/data.csv')
const rows = csv.parse(data)
const transformed = rows.map(row => ({ ...row, processed: true }))
writeJson('/app/output.json', transformed)
```

## Troubleshooting

### OutOfFuel on Simple Code

**Symptom:** Code looks simple but hits fuel limit.

**Likely Causes:**
1. Hidden heavy package import
2. Infinite loop (even short-running)
3. Recursive function without base case

**Diagnosis:**
```python
# Add print statements to isolate fuel consumption
result = sandbox.execute("""
print("Start")
import openpyxl  # <-- Suspect this
print("After import")
# ... rest of code
""")
# Check which print appears in stdout before OutOfFuel
```

**Solution:**
- Increase budget if heavy package detected
- Fix infinite loop/recursion if found

### Inconsistent Fuel Usage

**Symptom:** Same code consumes different fuel across runs.

**Likely Causes:**
1. Different sessions (cached vs. uncached imports)
2. Non-deterministic code (random, time-based)
3. Different input data sizes

**Diagnosis:**
```python
# Run multiple times in same session
results = []
for i in range(5):
    result = sandbox.execute(same_code)
    results.append(result.fuel_consumed)

print(f"Min: {min(results):,}, Max: {max(results):,}, Avg: {sum(results)/len(results):,}")
# If min << max, likely import caching effect
```

**Solution:**
- Use persistent sessions for consistency
- Pre-import heavy packages in session setup

### Budget Too Generous

**Symptom:** Fuel utilization consistently <20%.

**Impact:**
- Wasted resources in multi-tenant deployments
- Allows runaway code to execute longer

**Solution:**
```python
# Analyze current usage
if result.metadata['fuel_analysis']['utilization_percent'] < 20:
    current_budget = result.metadata['fuel_analysis']['budget']
    actual_usage = result.metadata['fuel_analysis']['consumed']
    optimized_budget = int(actual_usage * 2)  # 100% margin
    print(f"Reduce budget from {current_budget:,} to {optimized_budget:,}")
```

### Fuel Analysis Missing

**Symptom:** `fuel_analysis` not in `result.metadata`.

**Causes:**
1. Using old version of sandbox (pre-fuel-analysis)
2. Exception during execution prevented metadata population

**Solution:**
```python
if 'fuel_analysis' not in result.metadata:
    # Manual calculation
    utilization = (result.fuel_consumed / policy.fuel_budget) * 100
    print(f"Manual utilization: {utilization:.1f}%")
```

## Best Practices Summary

1. ✅ **Start generous, then optimize**: Begin with 20-30B budget, profile actual usage, tune down
2. ✅ **Use persistent sessions**: Cache heavy imports for 100x+ fuel savings
3. ✅ **Monitor fuel_analysis**: Use automated recommendations in metadata
4. ✅ **Pre-import in setup**: Front-load heavy packages in session creation
5. ✅ **Add safety margins**: Production budgets should be 50-100% above profiled usage
6. ✅ **Choose light alternatives**: XlsxWriter over openpyxl if write-only
7. ✅ **Chunk large workloads**: Process in batches to stay within limits
8. ✅ **Profile before deploying**: Test with realistic data volumes

## API Reference

### Setting Fuel Budget

```python
# Via ExecutionPolicy
from sandbox import create_sandbox, RuntimeType, ExecutionPolicy

policy = ExecutionPolicy(fuel_budget=20_000_000_000)
sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)

# Via MCP tool (create_session)
{
    "tool": "create_session",
    "arguments": {
        "language": "python",
        "fuel_budget": 20000000000
    }
}
```

### Reading Fuel Consumption

```python
result = sandbox.execute(code)

# Basic fuel data (always present)
print(result.fuel_consumed)  # Instructions executed

# Advanced fuel analysis (if available)
if 'fuel_analysis' in result.metadata:
    analysis = result.metadata['fuel_analysis']
    print(f"Status: {analysis['status']}")
    print(f"Utilization: {analysis['utilization_percent']:.1f}%")
    print(f"Recommended budget: {analysis.get('suggested_budget', 'N/A')}")
```

## Related Documentation

- [Error Guidance Catalog](ERROR_GUIDANCE.md) - OutOfFuel error solutions
- [Python Capabilities](PYTHON_CAPABILITIES.md) - Package details and requirements
- [JavaScript Capabilities](JAVASCRIPT_CAPABILITIES.md) - JavaScript fuel characteristics
- [MCP Integration Guide](MCP_INTEGRATION.md) - Using fuel analysis via MCP tools
- [WASM Sandbox Architecture](../WASM_SANDBOX.md) - How fuel metering works

## Appendix: Fuel Benchmarks

### Python Standard Library (No sys.path needed)

| Operation | Approximate Fuel | Notes |
|-----------|-----------------|-------|
| `print("Hello")` | 1-5M | Minimal overhead |
| `sum(range(1000))` | 5-10M | Simple loop |
| `import json` | 50-100M | Lightweight stdlib |
| `import re` | 100-200M | Regex engine |
| `import pathlib` | 50-100M | Path handling |

### Data Structure Operations (per 1000 items)

| Operation | Approximate Fuel |
|-----------|-----------------|
| List append | 10-20M |
| Dict set | 20-30M |
| List comprehension | 5-10M |
| Dict comprehension | 15-25M |
| Sort list | 30-50M |

### File I/O (Small files <1MB)

| Operation | Approximate Fuel |
|-----------|-----------------|
| `open().read()` | 10-50M |
| `open().write()` | 10-50M |
| `json.load()` | 50-100M |
| `json.dump()` | 50-100M |

**Note:** Fuel consumption scales with file size and data complexity.

---

**Last Updated:** November 24, 2025  
**Related Change Proposal:** `openspec/changes/harden-mcp-tool-precision/`  
**Feedback:** File issues or PRs in the repository
