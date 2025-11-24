# Design: Hardening MCP Tool Precision & Error Guidance

## Context

The LLM WASM Sandbox provides secure code execution for Python and JavaScript via Model Context Protocol (MCP) tools. Following extensive testing (20+ scenarios, 57 tool invocations, 0% error rate), we identified that while the technical implementation is robust, the **interface layer** lacks precision for optimal LLM decision-making.

**Current State**:
- MCP tools have minimal descriptions (1-2 sentences)
- Errors are technically correct but lack actionable guidance
- Fuel budgets are opaque until exhaustion occurs
- Common patterns (session management, package usage) are undocumented at tool level

**Stakeholders**:
- LLMs consuming MCP tools (primary: Claude via MCP, future: other agents)
- Developers using sandbox library directly (via Python API)
- MCP client developers integrating with sandbox

**Constraints**:
- Must maintain backward compatibility (existing clients can't break)
- Performance overhead must be minimal (<1% execution time)
- Error detection must be reliable (low false positive rate)
- Documentation links must remain valid as codebase evolves

## Goals / Non-Goals

### Goals
1. **Improve LLM Tool Selection Accuracy**: Enhanced tool descriptions enable informed decisions (target: >95% correct tool choice)
2. **Reduce Error Resolution Time**: Actionable error guidance enables first-attempt fixes (target: >80% resolution without retry)
3. **Proactive Fuel Management**: Fuel analysis prevents unexpected OutOfFuel errors (target: <5% fuel exhaustion rate)
4. **Maintain Backward Compatibility**: Existing clients work unchanged

### Non-Goals
1. **Automatic Error Recovery**: Not implementing auto-retry or code fixing
2. **ML-Based Error Detection**: Using rule-based pattern matching only
3. **Real-Time Monitoring Dashboard**: Metrics collection only, no UI in this change
4. **Package Installation**: Not adding dynamic package installation (WASI limitation)
5. **Code Linting/Validation**: Not implementing pre-execution validation

## Decisions

### Decision 1: Use `SandboxResult.metadata` for New Fields

**Options Considered**:
1. Add top-level fields to `SandboxResult` (e.g., `error_guidance`, `fuel_analysis`)
2. Use existing `metadata` dict for new structured content
3. Create separate `diagnostics` object

**Decision**: Use `metadata` dict

**Rationale**:
- ✅ Backward compatible (metadata is already an optional dict)
- ✅ Pydantic model validation still works (dict allows arbitrary keys)
- ✅ Existing clients ignore new keys automatically
- ✅ MCP server already uses `structured_content` pattern (natural mapping)
- ❌ Less type-safe than top-level fields (mitigated with TypedDict hints)

**Alternatives Rejected**:
- Top-level fields: Breaking change, requires versioning
- Separate diagnostics object: Adds complexity, no clear benefit

### Decision 2: Error Classification via Pattern Matching (Not ML)

**Options Considered**:
1. Rule-based pattern matching on stderr/trap messages
2. Machine learning classifier trained on error corpus
3. Heuristics + LLM-based error analysis

**Decision**: Rule-based pattern matching

**Rationale**:
- ✅ Deterministic and debuggable
- ✅ Zero model deployment overhead
- ✅ Fast (<10ms overhead target)
- ✅ Sufficient for common error patterns (covers >80% of cases)
- ❌ Requires manual pattern maintenance (acceptable trade-off)

**Alternatives Rejected**:
- ML classifier: Overkill for simple pattern matching, adds deployment complexity
- LLM-based: Latency too high (100ms+), introduces external dependency

### Decision 3: Fuel Analysis Thresholds (50/75/90)

**Options Considered**:
1. Fixed thresholds: 50% (moderate), 75% (warning), 90% (critical)
2. Adaptive thresholds based on historical data
3. Per-package fuel thresholds (different for openpyxl vs. tabulate)

**Decision**: Fixed thresholds (50/75/90)

**Rationale**:
- ✅ Simple to understand and implement
- ✅ Industry-standard alerting levels (similar to CPU/memory monitoring)
- ✅ Works well across different workload types
- ❌ May be too conservative for some workloads (mitigated by clear guidance)

**Alternatives Rejected**:
- Adaptive thresholds: Requires historical data, complex bootstrapping
- Per-package thresholds: Too fine-grained, maintenance burden

### Decision 4: Tool Description Enhancement via Docstring (Not JSON Schema)

**Options Considered**:
1. Embed guidance directly in tool description strings
2. Separate JSON schema with extended metadata
3. External documentation referenced from tools

**Decision**: Embed guidance in tool description strings

**Rationale**:
- ✅ LLMs receive guidance immediately (no extra lookups)
- ✅ FastMCP `@app.tool(description=...)` pattern supports rich text
- ✅ Single source of truth (description in code, not separate file)
- ❌ Description strings get long (mitigated with formatting)

**Alternatives Rejected**:
- JSON schema extension: MCP spec doesn't define extended metadata format
- External docs: Requires extra lookup step, LLMs may not follow links

### Decision 5: Session-Aware Fuel Analysis (Detect First Import)

**Options Considered**:
1. Track first import per session in session metadata
2. Assume all imports are first imports (conservative estimates)
3. Ignore import caching in fuel analysis

**Decision**: Track first import per session in session metadata

**Rationale**:
- ✅ Accurate fuel recommendations for repeat executions
- ✅ Helps LLMs understand import cost amortization
- ✅ Encourages persistent session usage for heavy packages
- ❌ Adds complexity to session metadata (acceptable for accuracy gain)

**Alternatives Rejected**:
- Conservative estimates: Overly pessimistic, confusing for cached imports
- Ignore caching: Misses opportunity to educate users on session benefits

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Server Layer                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ execute_code tool                                      │ │
│  │ - Enhanced description (usage patterns, pitfalls)      │ │
│  │ - Returns structured_content with error_guidance       │ │
│  │   and fuel_analysis                                    │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ create_session tool                                    │ │
│  │ - Enhanced description (decision tree, guidelines)     │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ list_runtimes / list_available_packages tools          │ │
│  │ - Enhanced responses (fuel reqs, API patterns)         │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Sandbox Core Layer                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ SandboxResult.metadata                                 │ │
│  │  {                                                     │ │
│  │    "error_guidance": {                                │ │
│  │      "error_type": "OutOfFuel",                       │ │
│  │      "actionable_guidance": [...],                    │ │
│  │      "related_docs": [...],                           │ │
│  │      "code_examples": [...]                           │ │
│  │    },                                                 │ │
│  │    "fuel_analysis": {                                 │ │
│  │      "consumed": 8500000000,                          │ │
│  │      "budget": 10000000000,                           │ │
│  │      "utilization_percent": 85.0,                     │ │
│  │      "status": "warning",                             │ │
│  │      "recommendation": "...",                         │ │
│  │      "likely_causes": [...]                           │ │
│  │    }                                                  │ │
│  │  }                                                    │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Analysis Layer (NEW)                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Error Classification (sandbox/host.py)                 │ │
│  │ - _classify_error(trap_reason, trap_message)          │ │
│  │ - _analyze_stderr(stderr, language)                   │ │
│  │ - Pattern matching: OutOfFuel, PathRestriction, etc.  │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Fuel Analysis (sandbox/core/fuel_patterns.py)         │ │
│  │ - _analyze_fuel_usage(consumed, budget)               │ │
│  │ - detect_heavy_packages(stderr)                       │ │
│  │ - generate_recommendations(status, patterns)          │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Error Templates (sandbox/core/error_templates.py)     │ │
│  │ - OUTOFFUEL_TEMPLATE                                  │ │
│  │ - PATH_RESTRICTION_TEMPLATE                           │ │
│  │ - QUICKJS_TUPLE_TEMPLATE                              │ │
│  │ - MISSING_VENDORED_PACKAGE_TEMPLATE                   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow: Error Guidance

```
1. Code execution fails (trap or non-zero exit code)
   ▼
2. sandbox/host.py: _classify_error(trap_reason, trap_message)
   - Matches trap_reason against known patterns
   - Returns error_type (e.g., "OutOfFuel")
   ▼
3. sandbox/host.py: _analyze_stderr(stderr, language)
   - Scans stderr for error patterns (FileNotFoundError, TypeError, etc.)
   - Returns error_type + context (e.g., detected file path)
   ▼
4. sandbox/core/error_templates.py: get_error_guidance(error_type, context)
   - Looks up template for error_type
   - Populates actionable_guidance, related_docs, code_examples
   - Returns structured error_guidance dict
   ▼
5. SandboxResult.metadata['error_guidance'] = error_guidance_dict
   ▼
6. MCP Server: execute_code tool returns structured_content
   - LLM receives actionable guidance in response
```

### Data Flow: Fuel Analysis

```
1. Code execution completes (success or failure)
   ▼
2. sandbox/host.py: _analyze_fuel_usage(consumed, budget)
   - Calculate utilization_percent = (consumed / budget) * 100
   - Classify status: efficient | moderate | warning | critical | exhausted
   ▼
3. sandbox/core/fuel_patterns.py: detect_patterns(stderr, consumed)
   - detect_heavy_packages(stderr) → detects openpyxl, PyPDF2, jinja2
   - detect_large_dataset() → heuristic based on high fuel without packages
   - Returns likely_causes array
   ▼
4. generate_recommendation(status, utilization_percent, likely_causes)
   - Status-based templates (warning: "Consider increasing to 15B+")
   - Package-specific guidance (openpyxl detected: "Requires 5-7B")
   - Safety margin calculation (consumed 8B → recommend 15-20B)
   ▼
5. SandboxResult.metadata['fuel_analysis'] = {consumed, budget, utilization_percent, status, recommendation, likely_causes}
   ▼
6. MCP Server: execute_code tool returns structured_content
   - LLM receives proactive fuel guidance in response
```

## Risks / Trade-offs

### Risk 1: Pattern Matching False Positives

**Risk**: Stderr pattern matching may misclassify errors (e.g., user printing "OutOfFuel" in output)

**Mitigation**:
- Combine multiple signals (trap_reason + stderr patterns + exit_code)
- Require exact match for trap messages (not substring)
- Test with adversarial inputs (user code trying to trigger false positives)
- Prioritize trap-based classification over stderr patterns

**Trade-off**: Accept <5% false positive rate for 80%+ coverage of common errors

### Risk 2: Documentation Link Rot

**Risk**: Error guidance `related_docs` links may break as documentation evolves

**Mitigation**:
- Use relative paths from repo root (docs/PYTHON_CAPABILITIES.md)
- Add link validation test (`tests/test_doc_links.py`)
- CI/CD check: fail if referenced docs don't exist or sections missing
- Document link maintenance in CONTRIBUTING.md

**Trade-off**: Manual link maintenance vs. no links (no links = less helpful)

### Risk 3: Fuel Recommendation Inaccuracy

**Risk**: Fuel recommendations may be too conservative (wasteful) or too aggressive (still hit limits)

**Mitigation**:
- Use 50-100% safety margin (conservative by default)
- Track recommendation effectiveness via metrics (do users hit OutOfFuel after following recommendation?)
- Iterative tuning based on observed patterns
- Session-aware analysis accounts for import caching

**Trade-off**: Conservative recommendations waste fuel budget vs. aggressive recommendations cause failures

### Risk 4: Performance Overhead

**Risk**: Error classification + fuel analysis may add latency to execution

**Mitigation**:
- Limit stderr scanning to first 10KB (avoid regex on massive outputs)
- Cache compiled regex patterns
- Use simple arithmetic for fuel analysis (no expensive operations)
- Target <10ms overhead (<1% of typical 250-300ms executions)
- Benchmark in tests to ensure overhead stays low

**Trade-off**: Analysis completeness vs. performance (10KB stderr limit may miss errors buried deep)

### Risk 5: Maintenance Burden

**Risk**: Error templates and fuel pattern mappings require ongoing maintenance as packages/runtimes evolve

**Mitigation**:
- Centralize patterns in `error_templates.py` and `fuel_patterns.py`
- Document pattern format and update process
- Use data-driven approach: log unclassified errors, add templates for common ones
- Version fuel requirements in package metadata (future: automate via package manifest)

**Trade-off**: Manual maintenance vs. incomplete coverage (incomplete coverage = some errors lack guidance)

## Migration Plan

### Phase 1: Additive Changes Only (Week 1-2)

1. Add new `metadata` fields to `SandboxResult` (backward compatible)
2. Update MCP tool descriptions (no API changes)
3. Deploy to staging environment
4. Test with existing clients: verify they ignore new fields

### Phase 2: Enable Error Guidance (Week 2-3)

1. Implement error classification logic
2. Populate `metadata.error_guidance` in results
3. Update MCP server to surface error guidance
4. A/B test with Claude Desktop: measure error resolution improvement

### Phase 3: Enable Fuel Analysis (Week 3-4)

1. Implement fuel analysis logic
2. Populate `metadata.fuel_analysis` in results
3. Update MCP server to surface fuel recommendations
4. Monitor fuel exhaustion rates: verify reduction

### Rollback Plan

If issues arise:
1. **Tool descriptions**: Revert to minimal descriptions (no code changes needed)
2. **Error guidance**: Set feature flag to disable population of `metadata.error_guidance`
3. **Fuel analysis**: Set feature flag to disable population of `metadata.fuel_analysis`
4. No database migrations or schema changes required (all metadata-based)

## Open Questions

1. **Q**: Should we add a new MCP tool `get_execution_guidance(code, language)` for pre-flight analysis?
   **A**: Deferred to future change - focus on post-execution guidance first

2. **Q**: Should fuel analysis track import costs per session in persistent storage (SQLite)?
   **A**: No - use in-memory session metadata only (avoid persistent storage complexity)

3. **Q**: Should we expose error guidance via structured logging (for observability)?
   **A**: Yes - add to `SandboxLogger` events for centralized monitoring

4. **Q**: Should error templates be localized for non-English LLMs?
   **A**: Deferred - all current MCP clients use English, revisit if internationalization needed

5. **Q**: Should we version the `metadata` schema (e.g., `metadata.schema_version: 1`)?
   **A**: No - optional dict pattern is self-describing, clients check key existence

## Success Criteria

### Quantitative Metrics

| Metric | Baseline | Target | Measurement Method |
|--------|----------|--------|-------------------|
| LLM tool selection accuracy | Unknown | >95% | Manual review of 100 MCP interactions |
| First-attempt error resolution | Unknown | >80% | Track executions with errors that don't retry same error |
| Fuel exhaustion rate | Unknown | <5% | (OutOfFuel errors) / (total executions) |
| Pattern classification coverage | N/A | >80% | (classified errors) / (total errors) |
| Performance overhead | N/A | <1% | Fuel analysis + error classification time / execution time |

### Qualitative Metrics

- [ ] Tool descriptions are clear and actionable (developer review)
- [ ] Error guidance leads to correct fixes (sample manual review)
- [ ] Fuel recommendations are accurate (no repeated OutOfFuel after following guidance)
- [ ] Documentation links remain valid (CI check passes)

## References

- Original PRD: `HARDENING.md`
- MCP Integration Guide: `docs/MCP_INTEGRATION.md`
- Python Capabilities: `docs/PYTHON_CAPABILITIES.md`
- JavaScript Capabilities: `docs/JAVASCRIPT_CAPABILITIES.md`
- MCP Specification: https://modelcontextprotocol.io/specification
- Wasmtime Fuel Metering: https://docs.wasmtime.dev/api/wasmtime/struct.Store.html#fuel
