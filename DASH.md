# PRD: Add POSIX Shell Runtime via `dash.wasm` to LLM WASM Sandbox

## 1. Overview

### 1.1 Summary

We will add a **POSIX shell runtime** to the [`llm-wasm-sandbox`](https://github.com/ThomasRohde/llm-wasm-sandbox) using a **WASI-compiled `dash.wasm`** binary.

This runtime will allow LLMs (and human users) to execute **portable POSIX shell scripts** inside the sandbox, with:

- Strict sandboxing via WASI (no host escape).
- Ephemeral command execution (`dash -c "<script>"`).
- Controlled access to a virtual filesystem and environment variables.
- Consistent request/response interface aligned with other runtimes (e.g. Python / QuickJS).

We **explicitly do not** aim for full GNU Bash compatibility in v1; this is `/bin/sh`-style Dash.

---

## 2. Motivation & Context

### 2.1 Problem

The current sandbox supports running code in one or more languages (e.g. Python, QuickJS), but:

- There is **no shell runtime** to orchestrate common CLI-like workflows (pipes, redirection, chaining small commands).
- LLMs are very good at emitting shell snippets, but cannot currently execute them inside `llm-wasm-sandbox`.

### 2.2 Why `dash.wasm`?

- Dash is a **small, POSIX-compliant `/bin/sh`** implementation.
- It has an existing **WASM/WASI build** (`dash.wasm`) that can be used as a standalone CLI-like module.
- The semantics (portable POSIX sh vs Bash) are “good enough” and predictable for LLMs, as long as we **document the constraints**.

### 2.3 Target Audience

- **LLM tool authors** using `llm-wasm-sandbox` to run untrusted code.
- **Developers** prototyping agentic workflows that need shell commands (e.g. `grep`, `sed`, simple scripts).
- **Security-conscious teams** who want strict confinement while still enabling reasonably powerful scripting.

---

## 3. Goals and Non-Goals

### 3.1 Goals

1. **New Shell Runtime**
   - Add a new runtime type (e.g. `"sh"` or `"shell"`) that executes POSIX shell scripts via `dash.wasm`.

2. **Ephemeral, Single-Command Execution**
   - Each execution request corresponds to a single `dash -c "<script>"` run.
   - No persistent shell session or background jobs in v1.

3. **Consistent Runtime Interface**
   - Input: script, optional stdin, optional file map, env, timeout, resource limits.
   - Output: stdout, stderr, exit code, timing, and error metadata.
   - Fit into existing sandbox abstractions (Runtime interface / adapter pattern).

4. **Clear Semantics for LLMs**
   - Tool description and docs spell out:
     - “This is POSIX `/bin/sh` (Dash), **not** full GNU Bash.”
     - List of supported patterns (simple pipes, redirects, conditionals, loops).
     - Disallowed / not-guaranteed features (bash arrays, associative arrays, process substitution, etc).

5. **Security & Isolation**
   - Execution is fully sandboxed via WASI.
   - Access only to the **virtual filesystem** we provide.
   - No network access, no host syscalls beyond allowed WASI subset.

### 3.2 Non-Goals (v1)

- **No full Bash compatibility**
  - We will not attempt to emulate all Bashisms.
- **No persistent interactive shell sessions**
  - No REPL / multi-command session management in v1.
- **No advanced job control**
  - `&`, foreground/background signals, etc., are best-effort only if supported by Dash; not part of the contract.
- **No TTY / line editing**
  - Script execution only; no interactive command editing.

---

## 4. User Stories

1. **As an LLM**, I want to run:
   ```sh
   for f in *.txt; do
     echo "$f: $(wc -l < "$f") lines"
   done
````

so I can summarize files provided in the sandbox filesystem.

2. **As a developer**, I want to POST:

   ```json
   {
     "language": "sh",
     "code": "echo hello; ls",
     "files": [{ "path": "a.txt", "content": "hi" }]
   }
   ```

   and get back stdout/stderr/exitCode without touching the shell implementation details.

3. **As a security-conscious user**, I want all shell executions to be strictly sandboxed so scripts cannot access my host filesystem or network.

4. **As a tool designer**, I want a clear **tool description** explaining exactly what shell features are available so I can shape LLM prompts accordingly.

---

## 5. Functional Requirements

### 5.1 Runtime Identification

* **FR-1**: Introduce a new runtime ID, e.g.:

  * `"sh"` or `"shell"` or `"dash"`.
* **FR-2**: The runtime type must be selectable via the same mechanism that currently chooses Python/QuickJS/etc.

### 5.2 Execution API

Assuming a generic runtime execution interface, the shell runtime should support:

#### 5.2.1 Request Shape

* **FR-3**: Minimal request structure:

```ts
type ShellRuntimeId = "sh" | "shell" | "dash";

interface ShellExecutionRequest {
  runtime: ShellRuntimeId;        // e.g. "sh"
  code: string;                   // shell script to run with `dash -c`
  argv?: string[];                // optional extra arg list (beyond "-c <code>")
  stdin?: string;                 // optional stdin text
  env?: Record<string, string>;   // environment variables
  files?: SandboxFile[];          // preloaded files in the virtual FS
  cwd?: string;                   // virtual working directory
  timeoutMs?: number;             // hard timeout for execution
  maxOutputBytes?: number;        // truncation / safety limit
}

interface SandboxFile {
  path: string;                   // e.g. "/workspace/script.sh"
  content: string;                // utf-8 text or base64 if needed
  executable?: boolean;           // mark as executable if relevant
}
```

#### 5.2.2 Response Shape

* **FR-4**: Response from shell runtime:

```ts
interface ShellExecutionResult {
  stdout: string;                 // captured stdout (possibly truncated)
  stderr: string;                 // captured stderr (possibly truncated)
  exitCode: number | null;        // null if crashed/aborted before exit
  timedOut: boolean;              // true if timeout hit
  truncated: boolean;             // true if output truncated
  durationMs: number;             // wall-clock runtime
  error?: string;                 // error description, if any
}
```

* **FR-5**: All runtime-specific errors (e.g. WASM instantiation failure) must be surfaced via `error` with `exitCode = null`.

### 5.3 Execution Semantics

* **FR-6**: Each execution corresponds to **one Dash process** invoked as:

  * `dash -c "<code>"` plus `argv` as extra args.
* **FR-7**: `cwd` must be honored within the virtual filesystem if supported by the WASI host.
* **FR-8**: `stdin` must be piped into Dash’s standard input if provided.
* **FR-9**: `env` variables must be available to the script as usual (`$FOO`).

### 5.4 Virtual Filesystem

* **FR-10**: Files in `files` must be written into an in-memory or sandboxed filesystem **before** shell execution.
* **FR-11**: Paths should be absolute or relative to `cwd`. Recommended: mount a root like `/workspace` and drop files there.
* **FR-12**: The runtime must not expose host filesystem paths beyond configured sandbox roots.

### 5.5 Limits & Timeouts

* **FR-13**: `timeoutMs` must enforce a hard cap; on timeout:

  * Terminate the WASM instance.
  * Return `timedOut = true` and `error = "Execution timed out"`.
* **FR-14**: `maxOutputBytes` must be enforced for `stdout` and `stderr`:

  * If exceeded, truncate and set `truncated = true`.

---

## 6. Non-Functional Requirements

### 6.1 Security

* **NFR-1**: No direct access to host filesystem.
* **NFR-2**: No network access from inside the WASM sandbox.
* **NFR-3**: No arbitrary host syscalls beyond those permitted by WASI.

### 6.2 Performance

* **NFR-4**: Cold start for Dash should be acceptable for interactive use (target < 200–400 ms in typical browsers / environments).
* **NFR-5**: Execution path should reuse common WASI host infrastructure used by other runtimes where possible.

### 6.3 Reliability

* **NFR-6**: Failure to load `dash.wasm` should produce a clear error message and not crash the entire sandbox.
* **NFR-7**: Errors inside the script (non-zero exit) should be treated as a **successful execution** with non-zero `exitCode`, not as host errors.

---

## 7. Architecture & Design

### 7.1 High-Level Architecture

1. **WASM Module**

   * `dash.wasm` binary shipped in the repository (e.g. `public/wasm/dash.wasm` or similar).
2. **WASI Host / Runtime Adapter**

   * Reuse existing WASI integration (same pattern as WLR Python / QuickJS if they are WASI-based).
   * Provide `argv`, `env`, stdio, and FS pre-mounts.
3. **ShellRuntime**

   * Implements the shared `Runtime` or `Executor` interface used by the sandbox.
   * Orchestrates FS setup, WASM instantiation, and invocation of `_start`/`main`.

### 7.2 Module Loading

* Dash runtime should:

  * Lazily fetch/instantiate `dash.wasm` on first use.
  * Optionally cache the compiled module for subsequent runs.
* Pseudocode (TypeScript):

```ts
let dashModulePromise: Promise<WebAssembly.Module> | null = null;

async function getDashModule(): Promise<WebAssembly.Module> {
  if (!dashModulePromise) {
    dashModulePromise = (async () => {
      const res = await fetch("/wasm/dash.wasm");
      const buf = await res.arrayBuffer();
      return await WebAssembly.compile(buf);
    })();
  }
  return dashModulePromise;
}
```

### 7.3 WASI Integration

* Use your existing WASI wrapper (e.g. based on `@wasmer/wasi`, `@bytecodealliance/preview2-shim`, or similar).
* For each execution:

  1. Build `argv` as:

     ```ts
     const argv = ["dash", "-c", request.code, ...(request.argv ?? [])];
     ```
  2. Build `env` as combination of:

     * Default environment.
     * `request.env`.
  3. Mount an in-memory filesystem and write all `request.files`.
  4. Configure `stdin` from `request.stdin` if present.
  5. Capture `stdout` / `stderr` via WASI pipes.
  6. Run `_start` with `timeoutMs`.

### 7.4 Sandbox Filesystem Layout

Example layout:

* Mount a single volume `/workspace`:

  * All user files go into `/workspace/...`.
  * `cwd` defaults to `/workspace` (unless overridden).
* Implementation detail:

  * Use an in-memory FS between runs (clean per execution).
  * Optional: support “preset files” shared across runs (v2+).

### 7.5 Runtime Interface Integration

If you have an abstract runtime interface, extend it as:

```ts
interface BaseRuntime {
  id: string;                     // "python", "quickjs", "sh"
  execute(request: any): Promise<any>;
}

class ShellRuntime implements BaseRuntime {
  id = "sh";

  async execute(request: ShellExecutionRequest): Promise<ShellExecutionResult> {
    // 1. Prepare WASI instance
    // 2. Mount FS, write files
    // 3. Spawn dash with argv/env/stdin
    // 4. Enforce timeout & output limits
    // 5. Return ShellExecutionResult
  }
}
```

Register in your runtime registry/factory:

```ts
const runtimes: Record<string, BaseRuntime> = {
  python: new PythonRuntime(),
  quickjs: new QuickjsRuntime(),
  sh: new ShellRuntime(),
};
```

---

## 8. LLM Tooling & Documentation

### 8.1 Tool Description (for LLMs)

Example description for an LLM tool:

> **Name:** `run_shell`
>
> **Description:**
> Execute a POSIX-compliant shell script using `dash` (`/bin/sh`) compiled to WebAssembly and running in an isolated sandbox.
> This is **NOT** GNU Bash – avoid Bash-only extensions like arrays, associative arrays, process substitution, or `[[ ]]` tests. Use portable `/bin/sh` syntax instead.
>
> **Input:**
>
> * `code` (string): POSIX shell script to run, passed to `dash -c`.
> * `files` (optional list): files to create in the sandbox FS before running.
> * `env` (optional map): environment variables.
> * `stdin` (optional string): standard input for the script.
> * `cwd` (optional string): working directory (default `/workspace`).
> * `timeoutMs` (optional int): maximum execution time.
>
> **Output:**
>
> * `stdout` / `stderr` (strings): captured outputs (may be truncated).
> * `exitCode` (int or null): process exit code if available.
> * `timedOut` (bool): true if execution timed out.
> * `truncated` (bool): true if outputs were truncated.

### 8.2 Prompting Guidelines

Add docs stating:

* “Use simple POSIX `/bin/sh` features.”
* Examples of **good** patterns:

  * `for` loops, `while` loops.
  * `if`, `case`.
  * Simple pipelines and redirects.
* Examples to **avoid**:

  * `[[ ... ]]` test syntax.
  * `${array[0]}` and arrays in general.
  * `<(process substitution)` and named pipes except simple `|`.

---

## 9. UX / UI Considerations

### 9.1 Frontend Integration

If the sandbox has a UI:

* Add “Shell” as an option in a **language/runtime selector**.
* Provide:

  * A code editor with shell syntax highlighting (if available).
  * Tabs for `stdout` and `stderr`.
  * Status indicators (Exit code, duration, timeout).

### 9.2 Error Presentation

* If Dash returns non-zero exit:

  * Display: `Exit code: N`.
  * Show both stdout and stderr.
* If host-level failure (e.g. wasm load fails):

  * Show friendly error: “Shell runtime unavailable: <details>”.

---

## 10. Implementation Plan

### 10.1 Phases

1. **Phase 1 – Plumbing**

   * Add `dash.wasm` to repo (e.g. `public/wasm/dash.wasm`).
   * Implement `ShellRuntime` that:

     * Loads and instantiates Dash.
     * Supports minimal `code` + `stdout`/`stderr`/`exitCode`.
   * Manual test harness: simple calls like `echo hello` and `ls`.

2. **Phase 2 – Filesystem & Env**

   * Implement file injection from `files` into `/workspace`.
   * Honor `cwd` and `env` in Dash.
   * Add `stdin` support.

3. **Phase 3 – Limits & Timeouts**

   * Implement `timeoutMs`.
   * Implement `maxOutputBytes` and mark `truncated`.

4. **Phase 4 – UI & Docs**

   * Add UI runtime selector option (`Shell`).
   * Document tool for LLMs and humans.
   * Add examples in README / docs.

### 10.2 Acceptance Criteria

* [ ] Running a request with:

  ```json
  {
    "runtime": "sh",
    "code": "echo hello world"
  }
  ```

  returns `stdout = "hello world\n"`, `exitCode = 0`.

* [ ] Files injected via `files` are visible from the shell (e.g. `ls` shows them).

* [ ] `env` variables are accessible via `$VAR`.

* [ ] `timeoutMs` correctly terminates long-running scripts.

* [ ] `maxOutputBytes` correctly truncates extremely verbose output and sets `truncated = true`.

* [ ] Non-zero exit codes are surfaced correctly (e.g. `false` returns `exitCode = 1`).

* [ ] An LLM using the `run_shell` tool can:

  * Read a file.
  * Transform it.
  * Write a new file.
  * Print a summary to stdout.

---

## 11. Open Questions

1. **Runtime ID**

   * Final choice: `"sh"`, `"shell"`, or `"dash"`?
   * Recommendation: use `"sh"` as the external ID to emphasize POSIX semantics.

2. **Persistent Sessions (v2+)**

   * Do we want to support a stateful session model later (e.g. same FS and environment across multiple calls)?

3. **Pre-bundled Utilities**

   * For v1, rely only on built-in Dash functionalities.
   * For v2, consider bundling `coreutils`-style WASM binaries for richer CLI support.

---

## 12. Future Enhancements (Out of Scope for v1)

* **Full Bash Support**

  * Build and integrate a custom `bash.wasm`, exposing it as `"bash"` runtime.
* **Interactive REPL**

  * A terminal-like shell UI with pseudo-TTY in the browser.
* **Shared Volumes Between Runtimes**

  * Allow Python / JS / Shell to share a volume (`/workspace`) across executions.
* **Streaming Output**

  * Stream stdout/stderr incrementally to the UI instead of returning only at the end.


