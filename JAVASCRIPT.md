JavaScript (QuickJS) Sandbox Support
This PRD describes adding JavaScript runtime support to llm-wasm-sandbox using QuickJS. The goal is to allow safe, WASM-based execution of untrusted JS code under the same security model as the existing Python sandbox. The JavaScript sandbox must preserve all current constraints (no network/subprocess, strict filesystem isolation) and integrate cleanly with the existing API and configuration models.
Goals
Embed QuickJS WASM: Include a QuickJS engine compiled to WebAssembly (WASM/WASI) so it can run under Wasmtime. QuickJS is a small, embeddable JavaScript engine whose WASI-enabled build provides a standalone binary for running JS code
github.com
github.com
.
Secure Execution: Execute untrusted JS code in an isolated WASM sandbox. Reuse the existing WASI-based model: code is provided as a file (e.g. user_code.js), launched under Wasmtime, with no network/subprocess capabilities.
Resource Controls: Enforce deterministic limits via the ExecutionPolicy. CPU usage is limited by fuel (WASM instruction counter) and memory is capped (linear memory size)
GitHub
GitHub
. The sandbox must track fuel consumed and peak memory, and trap on limits. Infinite loops should be caught by fuel exhaustion (producing an “OutOfFuel” error)
GitHub
.
I/O and Outputs: Capture the sandbox’s standard output and error. The SandboxResult model already includes stdout and stderr fields for this purpose
GitHub
. The JavaScript sandbox should write console.log or other output to stdout, and any JS exceptions or runtime errors to stderr. Output must respect stdout_max_bytes/stderr_max_bytes caps from the policy.
Filesystem Isolation: Use WASI preopens to restrict file access. By default, only the workspace directory (mounted to /app) is visible to the JS code. Attempting to read/write outside /app must fail (just as it does for Python)
GitHub
. Absolute paths or “..” escapes should be prevented by WASI. Reads/writes within /app should work as usual (the host can place files there via the session API).
No Network/Subprocess: The QuickJS WASM should not allow network or subprocess calls. By default, WASI modules have no network capabilities, and QuickJS itself has no built-in networking. This preserves the sandbox’s “no network, no subprocess” rule
GitHub
.
REPL vs Script Execution: Provide at least file-based execution (JS code as a file). If feasible, allow a REPL-like mode (interactive, stateful execution) by keeping a runtime instance alive; otherwise focus on script execution. (In either case, code injection is similar to Python’s approach of writing a file and invoking the WASM binary with that file.)
API Integration: Add a new JavaScriptSandbox implementation under sandbox/runtimes/javascript/. Update the RuntimeType enum (already has JAVASCRIPT) and the factory function (create_sandbox) to instantiate the JS sandbox instead of raising NotImplemented
GitHub
GitHub
. The new sandbox should accept the same ExecutionPolicy, session_id, workspace_root, and optional wasm_binary_path for the QuickJS module (e.g. "bin/quickjs.wasm"). Its execute(code: str, …) method should mirror PythonSandbox: write code to /app/user_code.js, launch Wasmtime with the QuickJS module, and return a SandboxResult.
Testing: Add unit/integration tests for the JS sandbox. Test cases should mirror the Python tests: basic execution (console.log, import, etc.), environment variable injection, file I/O within /app, blocking of out-of-scope paths, fuel exhaustion (e.g. while(true) loop), memory limits (large arrays), and error handling. For example, a test for infinite loop should assert that result.success is false and "OutOfFuel" appears in stderr
GitHub
. The test suite should use create_sandbox(runtime=RuntimeType.JAVASCRIPT) and the same helper utilities as for Python.
QuickJS WASM Integration
QuickJS Engine: Use a WASI-compatible build of QuickJS. The quickjs-build-wasm project demonstrates building QuickJS to a standalone WASM module
github.com
. We should include a similar binary (e.g. quickjs.wasm). This binary will run on Wasmtime and accept a JS file to execute.
Binary Path: By analogy to the Python sandbox’s bin/python.wasm, we can place the QuickJS WASM file under bin/quickjs.wasm. Allow this path to be overridden via constructor kwargs (like wasm_binary_path).
Invocation: The JavaScript sandbox’s run sequence will look roughly like:
Create or reuse a session workspace (workspace_root/<session_id>).
Write the user’s code into, say, /app/user_code.js.
Construct the Wasmtime command. For example:
wasmtime --dir=/app --env=... --memory=<limit> --fuel=<limit> quickjs.wasm /app/user_code.js
(Using Wasmtime CLI or API with the given ExecutionPolicy settings.)
Collect the exit code, stdout, stderr. Populate a SandboxResult with these, along with fuel_consumed, memory_used_bytes, and any metadata.
Compilation References: QuickJS is known to compile to WASM/WASI
github.com
github.com
. We do not need to write the C build steps in this PRD, but the documentation should note that maintainers can use an existing WASM build (or follow quickjs-build-wasm’s instructions to rebuild if needed).
Security and Resource Limits
ExecutionPolicy: The new sandbox must honor the existing ExecutionPolicy model
GitHub
. That includes: fuel_budget (max WASM instructions), memory_bytes (max linear memory), stdout_max_bytes, stderr_max_bytes, and filesystem mounts (mount_host_dir, guest_mount_path etc). For JS, argv and env defaults from Python may not apply; the sandbox may ignore argv or provide a JS-appropriate version (e.g. default could be ["quickjs", "/app/user_code.js"]). Environment variables (from policy.env) should be limited or empty, as in Python only whitelisted vars are exposed
GitHub
.
Fuel Metering: Use Wasmtime’s fuel metering to stop runaway loops. On fuel exhaustion, the Wasmtime trap should be caught and reported. Tests should expect exit_code != 0 and an error message like "OutOfFuel" in stderr
GitHub
.
Memory Limit: Configure the WASM instance’s maximum memory to memory_bytes. Attempts to allocate beyond that should trap. The sandbox should catch such traps or Python-like MemoryError and include an appropriate message in stderr or stdout. The result’s memory_used_bytes should reflect peak usage.
Output Limits: Truncate stdout/stderr according to stdout_max_bytes/stderr_max_bytes. If the JS runtime generates more output than allowed, indicate truncation in the result metadata (e.g. stdout_truncated).
Filesystem Policy: Mirror Python’s use of WASI preopens: by default, only mount the host “workspace” directory at /app inside WASI. Do not grant access to ~ or other paths. Any file operations in JS (e.g. using QuickJS’s built-in file I/O or require('fs') in WASI mode) should only see /app. The Python tests use calls like open("/etc/passwd") to ensure blocking; similar JS tests (e.g. fs.readFile("/etc/passwd")) should fail.
GitHub
No Network/Subprocess: Ensure the QuickJS WASM is not given any non-file-system capabilities. By default, a WASI-compiled QuickJS has no syscall to open sockets or spawn processes. Document that the JavaScript sandbox will not support any form of networking or child processes, matching Python’s model
GitHub
.
Execution Model
Script Execution: The initial implementation should treat the entire user input as a script. Write it to user_code.js and run quickjs.wasm /app/user_code.js. This mirrors how the Python sandbox runs python -I /app/user_code.py.
Module Support: If QuickJS was built with modules enabled, allow import or require. The sandbox could support ES modules by running quickjs.wasm --module /app/user_code.js if needed. For simplicity, the first version can require scripts to be self-contained.
REPL Mode (Optional): As a bonus, the sandbox may allow a REPL-like interface. This could involve creating a persistent QuickJS runtime and feeding it code chunks (maintaining state). However, stateful REPL is more complex under WASM and may be postponed. At minimum, note in docs that each execute() call is a fresh runtime.
Integration Points
RuntimeType/Factory: Update the RuntimeType enum (already has JAVASCRIPT) and modify create_sandbox() in sandbox/core/factory.py. Instead of raising NotImplementedError for JS
GitHub
, it should import and return the new JavaScriptSandbox class. For example:
if runtime == RuntimeType.JAVASCRIPT:
    from sandbox.runtimes.javascript.sandbox import JavaScriptSandbox
    wasm_path = kwargs.pop("wasm_binary_path", "bin/quickjs.wasm")
    return JavaScriptSandbox(wasm_binary_path=wasm_path, policy=policy, 
                             session_id=session_id, workspace_root=workspace_root, logger=logger, **kwargs)
Cite [13†L19-L28] for how the factory dispatches based on RuntimeType.
New Sandbox Class: Create sandbox/runtimes/javascript/sandbox.py. It should follow the interface of PythonSandbox (likely a subclass of a common BaseSandbox). Its constructor accepts the WASM path and policy, and stores them. Implement an execute(code: str, inject_setup: bool = False) method (or similar) that does the run sequence. Use the host’s logging/metrics conventions.
CLI/Examples: Update README and any demos to show JS usage. For example:
from sandbox import create_sandbox, RuntimeType
sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)
result = sandbox.execute('console.log("Hello from QuickJS");')
print(result.stdout)  # should print "Hello from QuickJS\n"
This confirms that console.log maps to stdout.
Session Files API: Ensure the ability to write files into the session (via the existing session-aware API, e.g. write_session_file) works for JS runs. The mounted /app path should contain those files.
Testing and Validation
Unit Tests: Add tests under tests/ similar to test_sandbox.py, but focusing on JS. For example:
Test Basic Output: Running a simple script (console.log) produces expected stdout.
Test Environment Variables: If implementing env passing, verify process.env or similar. (Optional, since JS may not easily access WASI env.)
Test FS Isolation: Attempts to access files outside /app (e.g. absolute paths, ..) should throw errors. Accessing /app/allowed.txt (written via write_session_file) should succeed.
Test Fuel Exhaustion: A JS infinite loop (while(true) {} or recursive function) with a low fuel_budget should stop and report failure, as in Python tests
GitHub
.
Test Memory Limits: Allocate a large array (let a = new Array(50_000_000)) and expect either a thrown error or trap.
Test Error Handling: A JS syntax error or exception should result in a non-zero exit code and the error message in stderr.
Integration Tests: Potentially reuse or extend existing Python sandbox tests to cover multi-turn sessions or logging. For example, start a session, write two different JS files in turn, ensure state doesn’t leak.
References and Constraints
The new JS sandbox must preserve all existing security constraints. As documented, the sandbox provides no network and no subprocess execution by design
GitHub
. These remain non-goals.
Use structured logging if available (SandboxLogger), as for PythonSandbox. Log execution start/stop events with the same schema.
Maintain typed models for requests and results. The existing SandboxResult model already covers output and metrics
GitHub
; ensure JavaScriptSandbox populates these fields correctly.
Keep the user-facing API simple: create_sandbox(runtime=RuntimeType.JAVASCRIPT) and sandbox.execute(js_code) should be the primary interface.
By following these requirements, we will add robust JavaScript execution capabilities to llm-wasm-sandbox while ensuring the same security posture as Python. All development should include appropriate unit/integration tests and documentation updates so that the feature can be shipped production-ready. Sources: The existing Python sandbox implementation and models provide the baseline for integration
GitHub
GitHub
. QuickJS’s WASM usage is confirmed by existing projects
github.com
github.com
. Existing tests illustrate expected behavior for limits and I/O
GitHub
GitHub
.
Citations

GitHub - lynzrand/quickjs-build-wasm: Build for QuickJS JavaScript Engine to WebAssembly

https://github.com/lynzrand/quickjs-build-wasm

GitHub - sebastianwessel/quickjs: A typescript package to execute JavaScript and TypeScript code in a webassembly quickjs sandbox

https://github.com/sebastianwessel/quickjs
GitHub
models.py

https://github.com/ThomasRohde/llm-wasm-sandbox/blob/245634a7dce9d4396af283a41a404d4269611f88/sandbox/core/models.py#L33-L42
GitHub
models.py

https://github.com/ThomasRohde/llm-wasm-sandbox/blob/245634a7dce9d4396af283a41a404d4269611f88/sandbox/core/models.py#L47-L56
GitHub
test_sandbox.py

https://github.com/ThomasRohde/llm-wasm-sandbox/blob/245634a7dce9d4396af283a41a404d4269611f88/tests/test_sandbox.py#L137-L141
GitHub
models.py

https://github.com/ThomasRohde/llm-wasm-sandbox/blob/245634a7dce9d4396af283a41a404d4269611f88/sandbox/core/models.py#L136-L143
GitHub
README.md

https://github.com/ThomasRohde/llm-wasm-sandbox/blob/245634a7dce9d4396af283a41a404d4269611f88/README.md#L48-L51
GitHub
factory.py

https://github.com/ThomasRohde/llm-wasm-sandbox/blob/245634a7dce9d4396af283a41a404d4269611f88/sandbox/core/factory.py#L156-L160
GitHub
factory.py

https://github.com/ThomasRohde/llm-wasm-sandbox/blob/245634a7dce9d4396af283a41a404d4269611f88/sandbox/core/factory.py#L20-L29
GitHub
models.py

https://github.com/ThomasRohde/llm-wasm-sandbox/blob/245634a7dce9d4396af283a41a404d4269611f88/sandbox/core/models.py#L91-L100