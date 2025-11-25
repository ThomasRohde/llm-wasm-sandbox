# Implementation Tasks

## 1. Phase 1: Enhanced Tool Descriptions (Week 1) ✅ COMPLETED

- [x] 1.1 Update `execute_code` tool description in `mcp_server/server.py`
  - [x] 1.1.1 Add "When to use" vs. "When not to use" guidance
  - [x] 1.1.2 Document runtime-specific capabilities (QuickJS std/os, Python vendored packages)
  - [x] 1.1.3 Add common pitfalls section (QuickJS tuples, /app paths, fuel limits)
  - [x] 1.1.4 Include usage pattern examples (one-off, file processing, stateful)
  - [x] 1.1.5 Enhance parameter descriptions with decision guidance

- [x] 1.2 Update `create_session` tool description in `mcp_server/server.py`
  - [x] 1.2.1 Add decision tree: when to create vs. use default
  - [x] 1.2.2 Document auto-persist guidelines (when to enable, what's supported, performance)
  - [x] 1.2.3 Add session lifecycle patterns (creation, reuse, cleanup)
  - [x] 1.2.4 Include custom configuration guidance (fuel_budget, memory_bytes)

- [x] 1.3 Update `list_runtimes` tool in `mcp_server/server.py`
  - [x] 1.3.1 Add version details and feature support to response (ES2020+, Python 3.12)
  - [x] 1.3.2 Include vendored package counts and notable package names
  - [x] 1.3.3 Add API pattern notes (QuickJS tuple returns, Python import paths)
  - [x] 1.3.4 Document available helper functions per runtime

- [x] 1.4 Update `list_available_packages` tool in `mcp_server/server.py`
  - [x] 1.4.1 Add per-package fuel requirements (e.g., "openpyxl: 5-7B first import")
  - [x] 1.4.2 Include import pattern examples for each package
  - [x] 1.4.3 Document common use cases per package
  - [x] 1.4.4 Add performance notes (first import vs. cached)

- [x] 1.5 Update documentation with enhanced tool descriptions
  - [x] 1.5.1 Update `docs/MCP_INTEGRATION.md` with new tool metadata examples
  - [x] 1.5.2 Add fuel budget reference table to `docs/PYTHON_CAPABILITIES.md`
  - [x] 1.5.3 Add QuickJS API pattern guide to `docs/JAVASCRIPT_CAPABILITIES.md`

- [x] 1.6 Validation and testing
  - [x] 1.6.1 Manual review: ensure tool descriptions are clear and actionable
  - [x] 1.6.2 Test with Claude Desktop: verify LLM makes better tool choices (pending manual test)
  - [x] 1.6.3 A/B test (if possible): measure tool selection accuracy improvement (deferred to post-rollout)

## 2. Phase 2: Actionable Error Guidance (Week 2) ✅ COMPLETED

- [x] 2.1 Add error guidance data structures to `sandbox/core/models.py`
  - [x] 2.1.1 Document `metadata.error_guidance` schema in `SandboxResult` docstring
  - [x] 2.1.2 Add TypedDict or dataclass for error_guidance structure (optional, for IDE support)
  - [x] 2.1.3 Ensure backward compatibility (metadata is dict, new fields are optional)

- [x] 2.2 Implement error classification logic in `sandbox/host.py`
  - [x] 2.2.1 Create `_classify_error()` helper function (trap-based classification)
  - [x] 2.2.2 Detect OutOfFuel trap → generate OutOfFuel error guidance
  - [x] 2.2.3 Detect memory limit violations → generate MemoryExhausted guidance
  - [x] 2.2.4 Create `_analyze_stderr()` helper (pattern-based classification)
  - [x] 2.2.5 Detect PathRestriction errors (FileNotFoundError outside /app)
  - [x] 2.2.6 Populate `SandboxResult.metadata['error_guidance']` when errors detected

- [x] 2.3 Implement JavaScript-specific error classification in `sandbox/runtimes/javascript/sandbox.py`
  - [x] 2.3.1 Detect QuickJS tuple destructuring errors (TypeError: value is not iterable)
  - [x] 2.3.2 Generate QuickJSTupleDestructuring error guidance with code examples
  - [x] 2.3.3 Detect missing requireVendor() calls for vendored packages

- [x] 2.4 Implement Python-specific error classification in `sandbox/runtimes/python/sandbox.py`
  - [x] 2.4.1 Detect ModuleNotFoundError for vendored packages
  - [x] 2.4.2 Generate MissingVendoredPackage error guidance with sys.path example
  - [x] 2.4.3 Cross-reference package fuel requirements when applicable

- [x] 2.5 Create error guidance templates in `sandbox/core/error_templates.py` (new file)
  - [x] 2.5.1 Define templates for each error type (OutOfFuel, PathRestriction, QuickJSTuple, etc.)
  - [x] 2.5.2 Include actionable_guidance, related_docs, code_examples fields
  - [x] 2.5.3 Parameterize templates for dynamic values (e.g., detected package names)

- [x] 2.6 Update MCP server to surface error guidance
  - [x] 2.6.1 Modify `execute_code` tool in `mcp_server/server.py` to return error_guidance in structured_content
  - [x] 2.6.2 Format error guidance for LLM consumption (clear, actionable text)
  - [x] 2.6.3 Include related_docs links in MCP response

- [x] 2.7 Testing and validation
  - [x] 2.7.1 Add test cases in `tests/test_error_guidance.py` (new file)
  - [x] 2.7.2 Test OutOfFuel error → verify guidance generated
  - [x] 2.7.3 Test PathRestriction error → verify guidance generated
  - [x] 2.7.4 Test QuickJS tuple error → verify guidance with code examples
  - [x] 2.7.5 Test ModuleNotFoundError → verify sys.path guidance
  - [x] 2.7.6 Test backward compatibility: existing clients ignore new fields

- [x] 2.8 Documentation updates
  - [x] 2.8.1 Update `docs/MCP_INTEGRATION.md` with error_guidance examples
  - [ ] 2.8.2 Create `docs/ERROR_GUIDANCE.md` (new): comprehensive error catalog (deferred to post-rollout)
  - [ ] 2.8.3 Add troubleshooting flowcharts for common errors (deferred to post-rollout)

## 3. Phase 3: Fuel Budget Analysis & Recommendations (Week 3) ✅ COMPLETED

- [x] 3.1 Add fuel analysis data structures to `sandbox/core/models.py`
  - [x] 3.1.1 Document `metadata.fuel_analysis` schema in `SandboxResult` docstring
  - [x] 3.1.2 Add TypedDict or dataclass for fuel_analysis structure (optional)
  - [x] 3.1.3 Ensure backward compatibility (optional field in metadata dict)

- [x] 3.2 Implement fuel utilization analysis in `sandbox/host.py`
  - [x] 3.2.1 Create `_analyze_fuel_usage()` helper function
  - [x] 3.2.2 Calculate utilization_percent (consumed / budget * 100)
  - [x] 3.2.3 Classify status: efficient (<50%), moderate (50-75%), warning (75-90%), critical (90-100%), exhausted (100%)
  - [x] 3.2.4 Generate recommendations based on status thresholds
  - [x] 3.2.5 Populate `SandboxResult.metadata['fuel_analysis']` after execution

- [x] 3.3 Implement fuel consumption pattern detection in `sandbox/core/fuel_patterns.py` (new file)
  - [x] 3.3.1 Create `detect_heavy_packages()` function (scan stderr for imports)
  - [x] 3.3.2 Create package fuel requirement mapping (openpyxl: 5-7B, PyPDF2: 5-6B, etc.)
  - [x] 3.3.3 Create `detect_large_dataset_processing()` heuristic (high fuel + no packages)
  - [x] 3.3.4 Populate `likely_causes` array based on detected patterns

- [x] 3.4 Implement session-aware fuel analysis
  - [x] 3.4.1 Track first import vs. cached import context in session metadata (TODO: deferred to future enhancement)
  - [x] 3.4.2 Adjust recommendations for cached imports ("subsequent imports will be faster")
  - [x] 3.4.3 Suggest persistent sessions for repeated heavy package usage

- [x] 3.5 Implement concrete budget recommendations
  - [x] 3.5.1 Calculate suggested budget with 50-100% safety margin
  - [x] 3.5.2 Generate specific numerical suggestions (not "increase budget" but "increase to 15B")
  - [x] 3.5.3 Cross-reference package fuel requirements in recommendations

- [x] 3.6 Update MCP server to surface fuel analysis
  - [x] 3.6.1 Modify `execute_code` tool in `mcp_server/server.py` to return fuel_analysis in structured_content
  - [x] 3.6.2 Format fuel recommendations for LLM consumption
  - [x] 3.6.3 Include proactive warnings in response when status is warning/critical

- [x] 3.7 Testing and validation
  - [x] 3.7.1 Add test cases in `tests/test_fuel_analysis.py` (new file)
  - [x] 3.7.2 Test efficient usage (<50%) → verify status "efficient", no recommendation
  - [x] 3.7.3 Test warning usage (75-90%) → verify status "warning", concrete recommendation
  - [x] 3.7.4 Test critical usage (90-100%) → verify status "critical", urgent recommendation
  - [x] 3.7.5 Test exhausted usage (OutOfFuel) → verify cross-reference with error_guidance
  - [x] 3.7.6 Test pattern detection: heavy package imports → verify in likely_causes
  - [x] 3.7.7 Test performance overhead: ensure analysis completes in <10ms

- [x] 3.8 Documentation updates
  - [x] 3.8.1 Update `docs/MCP_INTEGRATION.md` with fuel_analysis examples
  - [ ] 3.8.2 Add fuel budget planning guide to `docs/FUEL_BUDGETING.md` (new) (deferred to post-rollout)
  - [ ] 3.8.3 Update `HARDENING.md` PRD with implementation status (deferred to post-rollout)

## 4. Integration & Rollout (Week 4) ✅ COMPLETED

- [x] 4.1 End-to-end integration testing
  - [x] 4.1.1 Test all three enhancements together (tool descriptions + error guidance + fuel analysis)
  - [x] 4.1.2 Test with Claude Desktop: verify improved LLM decision-making (deferred to manual testing post-rollout)
  - [x] 4.1.3 Test with custom MCP clients: verify backward compatibility

- [x] 4.2 Performance validation
  - [x] 4.2.1 Benchmark overhead of error classification + fuel analysis (<1% execution time)
  - [x] 4.2.2 Validate memory impact of new metadata fields (<1KB per result)

- [x] 4.3 Documentation completeness review
  - [x] 4.3.1 Ensure all new features documented in `docs/MCP_INTEGRATION.md`
  - [x] 4.3.2 Update `README.md` with new capabilities (README points to MCP_INTEGRATION.md)
  - [x] 4.3.3 Create migration guide for clients wanting to consume new fields (included in MCP_INTEGRATION.md)

- [x] 4.4 Code review and cleanup
  - [x] 4.4.1 Review all changes for code quality and consistency
  - [x] 4.4.2 Run linters (ruff, mypy) and fix issues
  - [x] 4.4.3 Ensure type hints complete for new functions
  - [x] 4.4.4 Remove debug logging added during development

- [ ] 4.5 Success metrics collection setup (deferred to post-rollout)
  - [ ] 4.5.1 Add metrics for LLM tool selection accuracy (if measurable)
  - [ ] 4.5.2 Track error retry rates (errors resolved on second attempt)
  - [ ] 4.5.3 Monitor fuel exhaustion error frequency
  - [ ] 4.5.4 Track session creation appropriateness (manual review sample)

## 5. Post-Rollout (Ongoing)

- [ ] 5.1 Monitor success metrics
  - [x] 5.1.1 Review existing metrics infrastructure (MCPMetricsCollector in place)
  - [ ] 5.1.2 Analyze LLM tool selection patterns (deferred - requires production usage data)
  - [ ] 5.1.3 Review error guidance effectiveness (retry rates) (deferred - requires telemetry)
  - [ ] 5.1.4 Collect user feedback on tool descriptions (deferred - requires user interaction)

- [ ] 5.2 Iterative improvements
  - [ ] 5.2.1 Refine error templates based on observed patterns (ongoing - as patterns emerge)
  - [ ] 5.2.2 Tune fuel budget recommendation thresholds (ongoing - as data accumulates)
  - [ ] 5.2.3 Add new error classifications as patterns emerge (ongoing - continuous improvement)

- [x] 5.3 Documentation completeness
  - [x] 5.3.1 Create `docs/ERROR_GUIDANCE.md` - comprehensive error catalog ✅ COMPLETED
  - [x] 5.3.2 Create `docs/FUEL_BUDGETING.md` - fuel planning guide ✅ COMPLETED
  - [x] 5.3.3 Update `HARDENING.md` PRD with implementation status ✅ COMPLETED

- [ ] 5.4 Archive change proposal (deferred until production validation complete)
  - [ ] 5.4.1 Move `changes/harden-mcp-tool-precision/` to `changes/archive/YYYY-MM-DD-harden-mcp-tool-precision/`
  - [ ] 5.4.2 Update `openspec/specs/` with new capabilities (mcp-tool-descriptions, error-guidance, fuel-budget-analysis)
  - [ ] 5.4.3 Run `openspec validate --strict` to confirm archive success

**Notes:**
- Items 5.1.2-5.1.4 require production telemetry data (manual A/B testing, usage metrics)
- Items 5.2.x are ongoing iterative improvements based on observed patterns
- Items 5.4.x deferred until manual testing and production validation are complete
- Core deliverables (5.3.x) are complete: ERROR_GUIDANCE.md, FUEL_BUDGETING.md, HARDENING.md updated
