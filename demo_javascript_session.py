"""
Demo script showing multi-turn JavaScript session workflow with file persistence.

This script demonstrates the JavaScript session management features including:
- Creating isolated session workspaces for JavaScript execution
- Multi-turn code execution with state persistence
- Host-side file operations (write, read, list)
- Session cleanup
- Workspace pruning for automated maintenance
"""

from sandbox import (
    RuntimeType,
    create_sandbox,
    delete_session_workspace,
    list_session_files,
    prune_sessions,
    read_session_file,
    write_session_file,
)


def main():
    print("=" * 70)
    print("JavaScript Session Management Demo: Multi-Turn Workflow")
    print("=" * 70)

    # Phase 1: Create session and initial execution
    print("\n[Phase 1] Creating JavaScript session and executing initial code...")
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)
    session_id = sandbox.session_id
    print(f"Session ID: {session_id}")

    code1 = """
// Generate task data using JavaScript
const tasks = [
    { id: 1, title: 'Setup QuickJS sandbox', status: 'complete' },
    { id: 2, title: 'Run JavaScript tests', status: 'complete' },
    { id: 3, title: 'Deploy to production', status: 'pending' }
];

const metadata = {
    version: '1.0',
    timestamp: '2024-01-15T10:30:00',
    runtime: 'QuickJS-NG'
};

const data = { tasks, metadata };

console.log(`Created task data with ${tasks.length} tasks`);
console.log(`Task 1: ${tasks[0].title} - ${tasks[0].status}`);
console.log(`Task 2: ${tasks[1].title} - ${tasks[1].status}`);
console.log(`Task 3: ${tasks[2].title} - ${tasks[2].status}`);

// Note: File I/O not available in QuickJS WASI
// Data must be passed through stdout/result or host-side operations
console.log('\\nData summary:');
console.log(JSON.stringify(data, null, 2));
"""

    result1 = sandbox.execute(code1)
    print(f"Execution 1 - Success: {result1.success}")
    print(f"Execution 1 - Output:\n{result1.stdout.strip()}")
    print(f"Execution 1 - Fuel consumed: {result1.fuel_consumed:,}")

    # Phase 2: Host-side file operations
    print("\n[Phase 2] Writing data from host side (since JS has no file I/O)...")
    task_data = """
[
  { "id": 1, "title": "Setup QuickJS sandbox", "status": "complete" },
  { "id": 2, "title": "Run JavaScript tests", "status": "complete" },
  { "id": 3, "title": "Deploy to production", "status": "pending" }
]
"""
    write_session_file(session_id, "tasks.json", task_data.strip())
    print("Written tasks.json from host side")

    # Phase 3: List files in session
    print("\n[Phase 3] Listing files in session workspace...")
    files = list_session_files(session_id)
    print(f"Files in session: {files}")

    # Phase 4: Read file from host side
    print("\n[Phase 4] Reading tasks.json from host side...")
    file_data = read_session_file(session_id, "tasks.json")
    print(f"File content:\n{file_data.decode('utf-8')}")

    # Phase 5: Write configuration from host
    print("\n[Phase 5] Writing config file from host...")
    config_data = """
{
  "filter_status": "pending",
  "output_format": "summary",
  "max_results": 10
}
"""
    write_session_file(session_id, "config.json", config_data.strip())
    print("Written config.json from host side")

    # Phase 6: Multi-turn execution - process data
    print("\n[Phase 6] Second execution - processing with session context...")
    sandbox2 = create_sandbox(session_id=session_id, runtime=RuntimeType.JAVASCRIPT)

    code2 = """
// Simulate reading config and processing tasks
// In real scenario, host would pass data or use file APIs if available

const config = {
    filter_status: 'pending',
    output_format: 'summary',
    max_results: 10
};

const tasks = [
    { id: 1, title: 'Setup QuickJS sandbox', status: 'complete' },
    { id: 2, title: 'Run JavaScript tests', status: 'complete' },
    { id: 3, title: 'Deploy to production', status: 'pending' }
];

// Process based on config
const filterStatus = config.filter_status;
const outputFormat = config.output_format;

const filteredTasks = tasks.filter(t => t.status === filterStatus);

console.log(`Processing ${filteredTasks.length} ${filterStatus} tasks`);
console.log(`Output format: ${outputFormat}`);

if (outputFormat === 'summary') {
    filteredTasks.forEach(task => {
        console.log(`  - Task #${task.id}: ${task.title}`);
    });
} else {
    console.log(JSON.stringify(filteredTasks, null, 2));
}

// Generate report summary
const totalTasks = tasks.length;
const completedTasks = tasks.filter(t => t.status === 'complete').length;
const pendingTasks = filteredTasks.length;

console.log('\\nTask Report');
console.log('===========');
console.log(`Total tasks: ${totalTasks}`);
console.log(`Completed: ${completedTasks}`);
console.log(`Pending: ${pendingTasks}`);
"""

    result2 = sandbox2.execute(code2)
    print(f"Execution 2 - Success: {result2.success}")
    print(f"Execution 2 - Output:\n{result2.stdout.strip()}")
    print(f"Execution 2 - Fuel consumed: {result2.fuel_consumed:,}")

    # Phase 7: Verify session isolation
    print("\n[Phase 7] Demonstrating session isolation...")
    sandbox_b = create_sandbox(runtime=RuntimeType.JAVASCRIPT)
    session_b_id = sandbox_b.session_id
    print(f"Created second session: {session_b_id}")

    result_b = sandbox_b.execute("console.log('New isolated session - no shared state')")
    print(f"Session B output: {result_b.stdout.strip()}")

    files_a = list_session_files(session_id)
    files_b = list_session_files(session_b_id)
    print(f"Session A has {len(files_a)} files: {files_a}")
    print(f"Session B has {len(files_b)} files: {files_b}")

    # Phase 8: Host generates report based on execution
    print("\n[Phase 8] Host generates report based on JavaScript execution...")
    report = f"""
JavaScript Execution Report
===========================
Session ID: {session_id}

Execution Summary:
- Executions: 2
- Total fuel consumed: {result1.fuel_consumed + result2.fuel_consumed:,}
- All executions successful: {result1.success and result2.success}

Files in workspace:
{chr(10).join(f"  - {f}" for f in files_a)}

Session B (isolated):
- Session ID: {session_b_id}
- Files: {len(files_b)}
- Demonstrates complete isolation between sessions
"""
    write_session_file(session_id, "report.txt", report.strip())
    print("Written execution report to report.txt")

    # Phase 9: Read final report
    print("\n[Phase 9] Reading generated report from host...")
    report_content = read_session_file(session_id, "report.txt")
    print("Report content:")
    print(report_content.decode("utf-8"))

    # Phase 10: Cleanup
    print("\n[Phase 10] Cleaning up sessions...")
    delete_session_workspace(session_id)
    delete_session_workspace(session_b_id)
    print(f"Deleted session workspaces: {session_id}, {session_b_id}")

    # Phase 11: Workspace Pruning Demo
    print("\n[Phase 11] Demonstrating workspace pruning...")
    print("Creating temporary JavaScript sessions for pruning demo...")

    # Create a few test sessions
    temp_sessions = []
    for i in range(3):
        temp_sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)
        temp_id = temp_sandbox.session_id
        temp_sandbox.execute(f"console.log('Temporary JavaScript session {i + 1}')")
        temp_sessions.append(temp_id)
        print(f"  Created temp session {i + 1}: {temp_id}")

    # Demonstrate dry-run pruning
    print("\nDry-run pruning (preview only, no deletions):")
    dry_result = prune_sessions(older_than_hours=0.0, dry_run=True)
    print(f"  {dry_result}")
    print(f"  Would delete {len(dry_result.deleted_sessions)} sessions")
    print(f"  Skipped {len(dry_result.skipped_sessions)} sessions (no metadata)")

    # Demonstrate actual pruning (aggressive threshold for demo)
    print("\nActual pruning (deleting sessions older than 0 hours for demo):")
    prune_result = prune_sessions(older_than_hours=0.0)
    print(f"  {prune_result}")
    print(
        f"  Deleted sessions: {prune_result.deleted_sessions[:3]}{'...' if len(prune_result.deleted_sessions) > 3 else ''}"
    )
    print(f"  Total reclaimed: {prune_result.reclaimed_bytes:,} bytes")

    # Verify sessions were deleted
    print("\nVerifying sessions were deleted:")
    from pathlib import Path

    for temp_id in temp_sessions:
        workspace_exists = (Path("workspace") / temp_id).exists()
        print(f"  {temp_id}: {'EXISTS' if workspace_exists else 'DELETED'}")

    print("\n" + "=" * 70)
    print("JavaScript Demo completed successfully!")
    print("=" * 70)
    print("\nKey Takeaways:")
    print("- JavaScript sessions provide isolated workspaces for execution")
    print("- Host-side file operations enable data persistence")
    print("- QuickJS WASI has limited file I/O (use host operations instead)")
    print("- Each session is completely isolated from others")
    print("- Workspace pruning enables automated cleanup of stale sessions")
    print("- JavaScript execution tracked with fuel and memory metrics")
    print("=" * 70)


if __name__ == "__main__":
    main()
