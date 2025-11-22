# Capability: Workspace Operations

## ADDED Requirements

### Requirement: List Session Files
The sandbox MUST provide an API to list files in a session workspace from host code.

#### Scenario: List all files in session
Given a session workspace containing "data.csv", "output.txt", and "results/summary.json"
When list_session_files(session_id) is called
Then it MUST return a list containing all three relative paths
And paths MUST be relative to session workspace root
And directories MAY be included or excluded (implementation choice, must be documented)

#### Scenario: List files with pattern filter
Given a session workspace with "data.csv", "results.csv", "output.txt"
When list_session_files(session_id, pattern="*.csv") is called
Then it MUST return only "data.csv" and "results.csv"
And pattern matching MUST support standard glob syntax

#### Scenario: List empty session workspace
Given a session workspace with no files
When list_session_files(session_id) is called
Then it MUST return an empty list
And no exception MUST be raised

#### Scenario: List files with custom workspace root
Given workspace_root=Path("/tmp/custom")
When list_session_files(session_id, workspace_root=workspace_root) is called
Then it MUST list files from "/tmp/custom/<session_id>/"

---

### Requirement: Read Session Files
The sandbox MUST provide an API to read file contents from session workspaces.

#### Scenario: Read text file from session
Given a session file "output.txt" containing "Hello World"
When read_session_file(session_id, "output.txt") is called
Then it MUST return the bytes b"Hello World"
And the operation MUST NOT modify the file

#### Scenario: Read binary file from session
Given a session file "data.bin" containing binary data
When read_session_file(session_id, "data.bin") is called
Then it MUST return the exact binary content as bytes
And no text encoding MUST be applied

#### Scenario: Read nested file
Given a session file "results/analysis/report.csv"
When read_session_file(session_id, "results/analysis/report.csv") is called
Then it MUST read from the nested path successfully

#### Scenario: Read nonexistent file
Given no file "missing.txt" in session workspace
When read_session_file(session_id, "missing.txt") is called
Then it MUST raise FileNotFoundError
And error message MUST indicate the missing file

#### Scenario: Reject path traversal in read
Given a malicious relative_path "../../../etc/passwd"
When read_session_file(session_id, "../../../etc/passwd") is called
Then it MUST raise ValueError
And error MUST indicate path escapes session workspace
And no file outside session workspace MUST be accessed

---

### Requirement: Write Session Files
The sandbox MUST provide an API to write files to session workspaces from host code.

#### Scenario: Write new file to session
Given session_id "abc-123" with empty workspace
When write_session_file(session_id, "config.json", b'{"setting": "value"}') is called
Then "workspace/abc-123/config.json" MUST be created
And the file content MUST equal b'{"setting": "value"}'

#### Scenario: Write nested file with directory creation
Given session workspace with no "reports" directory
When write_session_file(session_id, "reports/summary.txt", b"Summary") is called
Then "reports/" directory MUST be created automatically
And "reports/summary.txt" MUST contain b"Summary"

#### Scenario: Overwrite existing file with overwrite=True
Given session file "data.txt" containing "old content"
When write_session_file(session_id, "data.txt", b"new content", overwrite=True) is called
Then "data.txt" MUST contain "new content"
And old content MUST be replaced

#### Scenario: Reject overwrite with overwrite=False
Given session file "data.txt" containing "existing"
When write_session_file(session_id, "data.txt", b"new", overwrite=False) is called
Then it MUST raise FileExistsError
And "data.txt" MUST still contain "existing" (unchanged)

#### Scenario: Reject path traversal in write
Given a malicious relative_path "../../../tmp/evil.txt"
When write_session_file(session_id, "../../../tmp/evil.txt", b"data") is called
Then it MUST raise ValueError
And no file outside session workspace MUST be created

---

### Requirement: Delete Session Paths
The sandbox MUST provide an API to delete files and directories from session workspaces.

#### Scenario: Delete single file
Given session file "temp.txt"
When delete_session_path(session_id, "temp.txt") is called
Then "temp.txt" MUST be removed
And subsequent read_session_file(session_id, "temp.txt") MUST raise FileNotFoundError

#### Scenario: Delete empty directory
Given session directory "empty_folder/" with no contents
When delete_session_path(session_id, "empty_folder/") is called
Then "empty_folder/" MUST be removed

#### Scenario: Delete directory with recursive=True
Given session directory "data/" containing "file1.txt" and "file2.txt"
When delete_session_path(session_id, "data/", recursive=True) is called
Then "data/" and all contents MUST be removed

#### Scenario: Reject non-recursive delete of non-empty directory
Given session directory "data/" containing files
When delete_session_path(session_id, "data/", recursive=False) is called
Then it MUST raise OSError or equivalent
And "data/" and contents MUST remain unchanged

#### Scenario: Reject path traversal in delete
Given a malicious relative_path "../../../tmp/target"
When delete_session_path(session_id, "../../../tmp/target") is called
Then it MUST raise ValueError
And no path outside session workspace MUST be deleted

#### Scenario: Delete nonexistent path
Given no path "nonexistent.txt" in session
When delete_session_path(session_id, "nonexistent.txt") is called
Then it MUST raise FileNotFoundError
And operation MUST NOT be silent (explicit error handling required)

---

### Requirement: Path Validation and Security
All file operations MUST validate paths to prevent directory traversal attacks.

#### Scenario: Validate relative paths
Given any file operation with relative_path argument
When the path contains ".." components
Then the operation MUST resolve the path fully
And MUST verify the resolved path is within session workspace
And MUST raise ValueError if path escapes workspace

#### Scenario: Reject absolute paths
Given any file operation with relative_path="/etc/passwd"
When the operation attempts to resolve the path
Then it MUST raise ValueError
And error MUST indicate absolute paths are not allowed

#### Scenario: Resolve symlinks safely
Given a session symlink "link.txt" pointing to "/etc/passwd"
When any file operation accesses "link.txt"
Then the operation MUST resolve the symlink target
And MUST verify target is within session workspace
And MUST raise ValueError if target escapes workspace

#### Scenario: Normalize path separators
Given relative_path with mixed separators "data\\subdir/file.txt"
When the path is validated
Then it MUST be normalized to platform-appropriate separators
And validation MUST work correctly across Windows/Unix

---

### Requirement: Workspace Operations Logging
File operations MUST emit structured log events for observability.

#### Scenario: Log file list operation
Given list_session_files(session_id, pattern="*.csv") is called
When the operation completes
Then logger MUST emit "session.file.list" event
And event MUST include session_id, pattern, and file count

#### Scenario: Log file read operation
Given read_session_file(session_id, "data.txt") is called
When the file is read successfully
Then logger MUST emit "session.file.read" event
And event MUST include session_id, path="data.txt", and size_bytes

#### Scenario: Log file write operation
Given write_session_file(session_id, "output.txt", data) is called
When the file is written successfully
Then logger MUST emit "session.file.write" event
And event MUST include session_id, path="output.txt", and size_bytes

#### Scenario: Log file delete operation
Given delete_session_path(session_id, "temp.txt") is called
When the path is deleted successfully
Then logger MUST emit "session.file.delete" event
And event MUST include session_id and path="temp.txt"

---

### Requirement: Error Handling
File operations MUST provide clear, actionable error messages.

#### Scenario: File not found error
Given session workspace has no file "missing.txt"
When read_session_file(session_id, "missing.txt") is called
Then it MUST raise FileNotFoundError
And error message MUST include the relative path "missing.txt"
And error MUST NOT expose absolute host filesystem paths

#### Scenario: Permission error
Given a session file with read-only permissions (simulated)
When write_session_file(session_id, "readonly.txt", data, overwrite=True) is called
Then it MUST raise PermissionError
And error message MUST indicate permission issue

#### Scenario: Invalid session ID
Given session_id with path traversal characters "../invalid"
When any file operation is called with this session_id
Then it MUST raise ValueError during workspace resolution
And no filesystem operations MUST be attempted

---

### Requirement: Type Safety
File operations MUST provide complete type hints for IDE support and type checking.

#### Scenario: list_session_files type hints
Given list_session_files function signature
When inspected in an IDE
Then return type MUST be list[str]
And all parameters MUST have type hints

#### Scenario: read_session_file type hints
Given read_session_file function signature
When inspected in an IDE
Then return type MUST be bytes
And all parameters MUST have type hints

#### Scenario: write_session_file type hints
Given write_session_file function signature
When inspected in an IDE
Then data parameter type MUST be bytes | str
And return type MUST be None
And all parameters MUST have type hints

#### Scenario: Path validation helper type hints
Given internal _validate_session_path helper function
When used in file operations
Then it MUST have full type hints
And return type MUST be Path
And exceptions MUST be documented in docstring
