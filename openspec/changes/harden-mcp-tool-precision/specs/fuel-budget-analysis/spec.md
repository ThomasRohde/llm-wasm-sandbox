# Spec: Fuel Budget Analysis

## ADDED Requirements

### Requirement: Proactive Fuel Utilization Monitoring

The sandbox SHALL analyze fuel consumption relative to budget and provide proactive recommendations when utilization approaches limits.

#### Scenario: Efficient Fuel Usage (<50%)

- **WHEN** code execution consumes less than 50% of fuel budget
- **THEN** `SandboxResult.metadata` SHALL contain:
  ```json
  {
    "fuel_analysis": {
      "consumed": 2_500_000_000,
      "budget": 10_000_000_000,
      "utilization_percent": 25.0,
      "status": "efficient",
      "recommendation": null,
      "likely_causes": []
    }
  }
  ```

#### Scenario: Moderate Fuel Usage (50-75%)

- **WHEN** code execution consumes between 50% and 75% of fuel budget
- **THEN** `SandboxResult.metadata.fuel_analysis` SHALL contain:
  - `status`: "moderate"
  - `recommendation`: Informational message (e.g., "Code used 62% of fuel budget - acceptable for current workload")
  - `likely_causes`: Empty or detected patterns (e.g., ["Moderate data processing", "Standard package imports"])

#### Scenario: Warning Fuel Usage (75-90%)

- **WHEN** code execution consumes between 75% and 90% of fuel budget
- **THEN** `SandboxResult.metadata.fuel_analysis` SHALL contain:
  - `status`: "warning"
  - `recommendation`: "Code used 85% of fuel budget. Consider increasing budget to 15B+ instructions for similar workloads to avoid exhaustion."
  - `likely_causes`: Array of detected patterns (e.g., ["Heavy package import (openpyxl)", "Complex data processing (1000+ items)"])

#### Scenario: Critical Fuel Usage (90-100%)

- **WHEN** code execution consumes between 90% and 100% of fuel budget
- **THEN** `SandboxResult.metadata.fuel_analysis` SHALL contain:
  - `status`: "critical"
  - `recommendation`: "CRITICAL: Code used 97% of fuel budget. Increase budget to at least 20B instructions for future executions to prevent OutOfFuel errors."
  - `likely_causes`: Array of detected patterns (e.g., ["Multiple heavy packages imported", "Large dataset processing", "Complex algorithms"])

#### Scenario: Fuel Exhaustion (100%)

- **WHEN** code execution hits OutOfFuel trap
- **THEN** both `fuel_analysis` and `error_guidance` SHALL be populated:
  - `fuel_analysis.status`: "exhausted"
  - `fuel_analysis.recommendation`: "Execution exceeded budget. See error_guidance for solutions."
  - `error_guidance.error_type`: "OutOfFuel"
  - Cross-reference between the two structures for comprehensive guidance

### Requirement: Fuel Consumption Pattern Detection

The sandbox SHALL detect common fuel-intensive patterns based on stderr content, package imports, and execution characteristics.

#### Scenario: Heavy Package Import Detection

- **WHEN** code imports heavy packages (openpyxl, PyPDF2, jinja2)
- **THEN** fuel analysis SHALL:
  - Scan stderr for import statements or ModuleNotFoundError messages
  - Detect package names in code execution context (if available)
  - Include in `likely_causes`: "Heavy package import detected: openpyxl (requires 5-7B fuel)"

#### Scenario: Large Dataset Processing Detection

- **WHEN** code processes large datasets (heuristic: >70% fuel usage + no heavy packages detected)
- **THEN** fuel analysis SHALL:
  - Infer dataset processing from high fuel consumption without package imports
  - Include in `likely_causes`: "Complex data processing or large dataset detected"

#### Scenario: Multiple Package Imports Detection

- **WHEN** code imports multiple vendored packages
- **THEN** fuel analysis SHALL:
  - Detect multiple import statements in stderr or code
  - Include in `likely_causes`: "Multiple package imports (cumulative fuel cost)"

### Requirement: Session-Aware Fuel Analysis

Fuel analysis SHALL account for session caching to provide accurate recommendations distinguishing first import vs. cached execution costs.

#### Scenario: First Import in Session

- **WHEN** code executes first import of heavy package in new session
- **THEN** fuel analysis SHALL:
  - Note first import context in recommendation
  - Example: "First import of openpyxl consumed 6.5B fuel. Subsequent imports will use <100M fuel due to caching."

#### Scenario: Cached Import in Existing Session

- **WHEN** code executes in session with cached imports
- **THEN** fuel analysis SHALL:
  - Note cached context if fuel usage is unexpectedly low
  - Example: "Fuel usage low due to cached imports from previous executions in this session."

#### Scenario: Session Recommendation

- **WHEN** fuel analysis detects repeated heavy package usage
- **THEN** recommendation SHALL suggest:
  - "Consider using persistent session with auto_persist_globals=True to cache imports across executions"

### Requirement: Fuel Budget Recommendation Accuracy

Fuel budget recommendations SHALL provide concrete numerical suggestions based on observed consumption patterns.

#### Scenario: Incremental Budget Increase

- **WHEN** code uses 85% of 10B budget (8.5B consumed)
- **THEN** recommendation SHALL suggest specific increase:
  - "Consider increasing budget to 15B instructions (1.5x current consumption)"
  - Not: "Increase budget" (too vague)

#### Scenario: Safety Margin Recommendations

- **WHEN** providing budget recommendations
- **THEN** suggested budgets SHALL include 50-100% safety margin above observed consumption:
  - Consumed 8B → Recommend 15-20B (not 10B)
  - Consumed 15B → Recommend 25-30B

#### Scenario: Package-Specific Recommendations

- **WHEN** heavy package detected and fuel exceeded
- **THEN** recommendation SHALL reference package fuel requirements:
  - "openpyxl requires 5-7B fuel for first import. Increase budget to 15B+ for reliable openpyxl usage."

### Requirement: Backward Compatibility

Fuel analysis SHALL be added to existing `SandboxResult.metadata` field to preserve API compatibility.

#### Scenario: Existing Clients Ignore Fuel Analysis

- **WHEN** an existing client receives `SandboxResult` with `metadata.fuel_analysis`
- **THEN** the client SHALL:
  - Continue to work without changes
  - Ignore `fuel_analysis` field if not accessed
  - Still access `fuel_consumed` at top level for basic metrics

#### Scenario: New Clients Consume Fuel Analysis

- **WHEN** a new client accesses `result.metadata.get('fuel_analysis')`
- **THEN** the client SHALL:
  - Receive structured fuel analysis when available
  - Display recommendations to users proactively
  - Use `status` field for UI indicators (warning icons, etc.)

### Requirement: Performance Impact Minimization

Fuel analysis SHALL be computed with minimal overhead (<1% of execution time) to avoid impacting overall performance.

#### Scenario: Analysis Computation Overhead

- **WHEN** fuel analysis is performed
- **THEN** the computation SHALL:
  - Use simple arithmetic (consumed / budget * 100)
  - Avoid regex scanning of large stderr output (limit to first 10KB)
  - Cache package detection patterns for reuse
  - Complete in <10ms for typical executions
