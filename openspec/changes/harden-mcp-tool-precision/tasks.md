# Implementation Tasks

## 1. Phase 1: Enhanced Tool Descriptions (Week 1)

- [ ] 1.1 Update `execute_code` tool description in `mcp_server/server.py`
  - [ ] 1.1.1 Add "When to use" vs. "When not to use" guidance
  - [ ] 1.1.2 Document runtime-specific capabilities (QuickJS std/os, Python vendored packages)
  - [ ] 1.1.3 Add common pitfalls section (QuickJS tuples, /app paths, fuel limits)
  - [ ] 1.1.4 Include usage pattern examples (one-off, file processing, stateful)
  - [ ] 1.1.5 Enhance parameter descriptions with decision guidance

- [ ] 1.2 Update `create_session` tool description in `mcp_server/server.py`
  - [ ] 1.2.1 Add decision tree: when to create vs. use default
  - [ ] 1.2.2 Document auto-persist guidelines (when to enable, what's supported, performance)
  - [ ] 1.2.3 Add session lifecycle patterns (creation, reuse, cleanup)
  - [ ] 1.2.4 Include custom configuration guidance (fuel_budget, memory_bytes)

- [ ] 1.3 Update `list_runtimes` tool in `mcp_server/server.py`
  - [ ] 1.3.1 Add version details and feature support to response (ES2020+, Python 3.12)
  - [ ] 1.3.2 Include vendored package counts and notable package names
  - [ ] 1.3.3 Add API pattern notes (QuickJS tuple returns, Python import paths)
  - [ ] 1.3.4 Document available helper functions per runtime

- [ ] 1.4 Update `list_available_packages` tool in `mcp_server/server.py`
  - [ ] 1.4.1 Add per-package fuel requirements (e.g., "openpyxl: 5-7B first import")
  - [ ] 1.4.2 Include import pattern examples for each package
  - [ ] 1.4.3 Document common use cases per package
  - [ ] 1.4.4 Add performance notes (first import vs. cached)

- [ ] 1.5 Update documentation with enhanced tool descriptions
  - [ ] 1.5.1 Update `docs/MCP_INTEGRATION.md` with new tool metadata examples
  - [ ] 1.5.2 Add fuel budget reference table to `docs/PYTHON_CAPABILITIES.md`
  - [ ] 1.5.3 Add QuickJS API pattern guide to `docs/JAVASCRIPT_CAPABILITIES.md`

- [ ] 1.6 Validation and testing
  - [ ] 1.6.1 Manual review: ensure tool descriptions are clear and actionable
  - [ ] 1.6.2 Test with Claude Desktop: verify LLM makes better tool choices
  - [ ] 1.6.3 A/B test (if possible): measure tool selection accuracy improvement

## 2. Phase 2: Actionable Error Guidance (Week 2)

- [ ] 2.1 Add error guidance data structures to `sandbox/core/models.py`
  - [ ] 2.1.1 Document `metadata.error_guidance` schema in `SandboxResult` docstring
  - [ ] 2.1.2 Add TypedDict or dataclass for error_guidance structure (optional, for IDE support)
  - [ ] 2.1.3 Ensure backward compatibility (metadata is dict, new fields are optional)

- [ ] 2.2 Implement error classification logic in `sandbox/host.py`
  - [ ] 2.2.1 Create `_classify_error()` helper function (trap-based classification)
  - [ ] 2.2.2 Detect OutOfFuel trap → generate OutOfFuel error guidance
  - [ ] 2.2.3 Detect memory limit violations → generate MemoryExhausted guidance
  - [ ] 2.2.4 Create `_analyze_stderr()` helper (pattern-based classification)
  - [ ] 2.2.5 Detect PathRestriction errors (FileNotFoundError outside /app)
  - [ ] 2.2.6 Populate `SandboxResult.metadata['error_guidance']` when errors detected

- [ ] 2.3 Implement JavaScript-specific error classification in `sandbox/runtimes/javascript/sandbox.py`
  - [ ] 2.3.1 Detect QuickJS tuple destructuring errors (TypeError: value is not iterable)
  - [ ] 2.3.2 Generate QuickJSTupleDestructuring error guidance with code examples
  - [ ] 2.3.3 Detect missing requireVendor() calls for vendored packages

- [ ] 2.4 Implement Python-specific error classification in `sandbox/runtimes/python/sandbox.py`
  - [ ] 2.4.1 Detect ModuleNotFoundError for vendored packages
  - [ ] 2.4.2 Generate MissingVendoredPackage error guidance with sys.path example
  - [ ] 2.4.3 Cross-reference package fuel requirements when applicable

- [ ] 2.5 Create error guidance templates in `sandbox/core/error_templates.py` (new file)
  - [ ] 2.5.1 Define templates for each error type (OutOfFuel, PathRestriction, QuickJSTuple, etc.)
  - [ ] 2.5.2 Include actionable_guidance, related_docs, code_examples fields
  - [ ] 2.5.3 Parameterize templates for dynamic values (e.g., detected package names)

- [ ] 2.6 Update MCP server to surface error guidance
  - [ ] 2.6.1 Modify `execute_code` tool in `mcp_server/server.py` to return error_guidance in structured_content
  - [ ] 2.6.2 Format error guidance for LLM consumption (clear, actionable text)
  - [ ] 2.6.3 Include related_docs links in MCP response

- [ ] 2.7 Testing and validation
  - [ ] 2.7.1 Add test cases in `tests/test_error_guidance.py` (new file)
  - [ ] 2.7.2 Test OutOfFuel error → verify guidance generated
  - [ ] 2.7.3 Test PathRestriction error → verify guidance generated
  - [ ] 2.7.4 Test QuickJS tuple error → verify guidance with code examples
  - [ ] 2.7.5 Test ModuleNotFoundError → verify sys.path guidance
  - [ ] 2.7.6 Test backward compatibility: existing clients ignore new fields

- [ ] 2.8 Documentation updates
  - [ ] 2.8.1 Update `docs/MCP_INTEGRATION.md` with error_guidance examples
  - [ ] 2.8.2 Create `docs/ERROR_GUIDANCE.md` (new): comprehensive error catalog
  - [ ] 2.8.3 Add troubleshooting flowcharts for common errors

## 3. Phase 3: Fuel Budget Analysis & Recommendations (Week 3)

- [ ] 3.1 Add fuel analysis data structures to `sandbox/core/models.py`
  - [ ] 3.1.1 Document `metadata.fuel_analysis` schema in `SandboxResult` docstring
  - [ ] 3.1.2 Add TypedDict or dataclass for fuel_analysis structure (optional)
  - [ ] 3.1.3 Ensure backward compatibility (optional field in metadata dict)

- [ ] 3.2 Implement fuel utilization analysis in `sandbox/host.py`
  - [ ] 3.2.1 Create `_analyze_fuel_usage()` helper function
  - [ ] 3.2.2 Calculate utilization_percent (consumed / budget * 100)
  - [ ] 3.2.3 Classify status: efficient (<50%), moderate (50-75%), warning (75-90%), critical (90-100%), exhausted (100%)
  - [ ] 3.2.4 Generate recommendations based on status thresholds
  - [ ] 3.2.5 Populate `SandboxResult.metadata['fuel_analysis']` after execution

- [ ] 3.3 Implement fuel consumption pattern detection in `sandbox/core/fuel_patterns.py` (new file)
  - [ ] 3.3.1 Create `detect_heavy_packages()` function (scan stderr for imports)
  - [ ] 3.3.2 Create package fuel requirement mapping (openpyxl: 5-7B, PyPDF2: 5-6B, etc.)
  - [ ] 3.3.3 Create `detect_large_dataset_processing()` heuristic (high fuel + no packages)
  - [ ] 3.3.4 Populate `likely_causes` array based on detected patterns

- [ ] 3.4 Implement session-aware fuel analysis
  - [ ] 3.4.1 Track first import vs. cached import context in session metadata
  - [ ] 3.4.2 Adjust recommendations for cached imports ("subsequent imports will be faster")
  - [ ] 3.4.3 Suggest persistent sessions for repeated heavy package usage

- [ ] 3.5 Implement concrete budget recommendations
  - [ ] 3.5.1 Calculate suggested budget with 50-100% safety margin
  - [ ] 3.5.2 Generate specific numerical suggestions (not "increase budget" but "increase to 15B")
  - [ ] 3.5.3 Cross-reference package fuel requirements in recommendations

- [ ] 3.6 Update MCP server to surface fuel analysis
  - [ ] 3.6.1 Modify `execute_code` tool in `mcp_server/server.py` to return fuel_analysis in structured_content
  - [ ] 3.6.2 Format fuel recommendations for LLM consumption
  - [ ] 3.6.3 Include proactive warnings in response when status is warning/critical

- [ ] 3.7 Testing and validation
  - [ ] 3.7.1 Add test cases in `tests/test_fuel_analysis.py` (new file)
  - [ ] 3.7.2 Test efficient usage (<50%) → verify status "efficient", no recommendation
  - [ ] 3.7.3 Test warning usage (75-90%) → verify status "warning", concrete recommendation
  - [ ] 3.7.4 Test critical usage (90-100%) → verify status "critical", urgent recommendation
  - [ ] 3.7.5 Test exhausted usage (OutOfFuel) → verify cross-reference with error_guidance
  - [ ] 3.7.6 Test pattern detection: heavy package imports → verify in likely_causes
  - [ ] 3.7.7 Test performance overhead: ensure analysis completes in <10ms

- [ ] 3.8 Documentation updates
  - [ ] 3.8.1 Update `docs/MCP_INTEGRATION.md` with fuel_analysis examples
  - [ ] 3.8.2 Add fuel budget planning guide to `docs/FUEL_BUDGETING.md` (new)
  - [ ] 3.8.3 Update `HARDENING.md` PRD with implementation status

## 4. Integration & Rollout (Week 4)

- [ ] 4.1 End-to-end integration testing
  - [ ] 4.1.1 Test all three enhancements together (tool descriptions + error guidance + fuel analysis)
  - [ ] 4.1.2 Test with Claude Desktop: verify improved LLM decision-making
  - [ ] 4.1.3 Test with custom MCP clients: verify backward compatibility

- [ ] 4.2 Performance validation
  - [ ] 4.2.1 Benchmark overhead of error classification + fuel analysis (<1% execution time)
  - [ ] 4.2.2 Validate memory impact of new metadata fields (<1KB per result)

- [ ] 4.3 Documentation completeness review
  - [ ] 4.3.1 Ensure all new features documented in `docs/MCP_INTEGRATION.md`
  - [ ] 4.3.2 Update `README.md` with new capabilities
  - [ ] 4.3.3 Create migration guide for clients wanting to consume new fields

- [ ] 4.4 Code review and cleanup
  - [ ] 4.4.1 Review all changes for code quality and consistency
  - [ ] 4.4.2 Run linters (ruff, mypy) and fix issues
  - [ ] 4.4.3 Ensure type hints complete for new functions
  - [ ] 4.4.4 Remove debug logging added during development

- [ ] 4.5 Success metrics collection setup
  - [ ] 4.5.1 Add metrics for LLM tool selection accuracy (if measurable)
  - [ ] 4.5.2 Track error retry rates (errors resolved on second attempt)
  - [ ] 4.5.3 Monitor fuel exhaustion error frequency
  - [ ] 4.5.4 Track session creation appropriateness (manual review sample)

## 5. Post-Rollout (Ongoing)

- [ ] 5.1 Monitor success metrics
  - [ ] 5.1.1 Analyze LLM tool selection patterns
  - [ ] 5.1.2 Review error guidance effectiveness (retry rates)
  - [ ] 5.1.3 Collect user feedback on tool descriptions

- [ ] 5.2 Iterative improvements
  - [ ] 5.2.1 Refine error templates based on observed patterns
  - [ ] 5.2.2 Tune fuel budget recommendation thresholds
  - [ ] 5.2.3 Add new error classifications as patterns emerge

- [ ] 5.3 Archive change proposal
  - [ ] 5.3.1 Move `changes/harden-mcp-tool-precision/` to `changes/archive/YYYY-MM-DD-harden-mcp-tool-precision/`
  - [ ] 5.3.2 Update `openspec/specs/` with new capabilities (mcp-tool-descriptions, error-guidance, fuel-budget-analysis)
  - [ ] 5.3.3 Run `openspec validate --strict` to confirm archive success
