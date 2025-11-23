"""
Demo script showing multi-turn session workflow with file persistence.

This script demonstrates the session management features including:
- Creating isolated session workspaces
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
    print("Session Management Demo: Multi-Turn Workflow")
    print("=" * 70)

    # Phase 1: Create session and initial execution
    print("\n[Phase 1] Creating session and executing initial code...")
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
    session_id = sandbox.session_id
    print(f"Session ID: {session_id}")

    code1 = """
import json

# Generate some data and save to file
data = {
    'tasks': [
        {'id': 1, 'title': 'Setup sandbox', 'status': 'complete'},
        {'id': 2, 'title': 'Run tests', 'status': 'complete'},
        {'id': 3, 'title': 'Deploy', 'status': 'pending'}
    ],
    'metadata': {
        'version': '1.0',
        'timestamp': '2024-01-15T10:30:00'
    }
}

with open('/app/tasks.json', 'w') as f:
    json.dump(data, f, indent=2)

print("Created tasks.json with", len(data['tasks']), "tasks")
"""

    result1 = sandbox.execute(code1)
    print(f"Execution 1 - Success: {result1.success}")
    print(f"Execution 1 - Output: {result1.stdout.strip()}")
    print(f"Execution 1 - Fuel consumed: {result1.fuel_consumed:,}")

    # Phase 2: List files in session
    print("\n[Phase 2] Listing files in session workspace...")
    files = list_session_files(session_id)
    print(f"Files in session: {files}")

    # Phase 3: Read file from host side
    print("\n[Phase 3] Reading tasks.json from host side...")
    file_data = read_session_file(session_id, "tasks.json")
    print(f"File content (first 100 chars): {file_data[:100].decode('utf-8')}...")

    # Phase 4: Write configuration from host
    print("\n[Phase 4] Writing config file from host...")
    config_data = b"""
# Configuration for task processor
FILTER_STATUS=pending
OUTPUT_FORMAT=summary
"""
    write_session_file(session_id, "config.txt", config_data.strip())
    print("Written config.txt from host side")

    # Phase 5: Multi-turn execution - read and process
    print("\n[Phase 5] Second execution - processing with persistence...")
    sandbox2 = create_sandbox(session_id=session_id, runtime=RuntimeType.PYTHON)

    code2 = """
import json

# Read the config file written by host
with open('/app/config.txt', 'r') as f:
    config = {}
    for line in f:
        if '=' in line and not line.startswith('#'):
            key, value = line.strip().split('=', 1)
            config[key] = value

# Read the tasks created in previous execution
with open('/app/tasks.json', 'r') as f:
    data = json.load(f)

# Process based on config
filter_status = config.get('FILTER_STATUS', 'all')
output_format = config.get('OUTPUT_FORMAT', 'full')

pending_tasks = [t for t in data['tasks'] if t['status'] == filter_status]

print(f"Processing {len(pending_tasks)} {filter_status} tasks")
print(f"Output format: {output_format}")

if output_format == 'summary':
    for task in pending_tasks:
        print(f"  - Task #{task['id']}: {task['title']}")
else:
    print(json.dumps(pending_tasks, indent=2))

# Save summary report
with open('/app/report.txt', 'w') as f:
    f.write(f"Task Report\\n")
    f.write(f"===========\\n")
    f.write(f"Total tasks: {len(data['tasks'])}\\n")
    f.write(f"Pending: {len(pending_tasks)}\\n")
    f.write(f"Completed: {len([t for t in data['tasks'] if t['status'] == 'complete'])}\\n")
"""

    result2 = sandbox2.execute(code2)
    print(f"Execution 2 - Success: {result2.success}")
    print(f"Execution 2 - Output:\n{result2.stdout.strip()}")
    print(f"Execution 2 - Fuel consumed: {result2.fuel_consumed:,}")

    # Phase 6: Verify session isolation
    print("\n[Phase 6] Demonstrating session isolation...")
    sandbox_b = create_sandbox(runtime=RuntimeType.PYTHON)
    session_b_id = sandbox_b.session_id
    print(f"Created second session: {session_b_id}")

    result_b = sandbox_b.execute("import os; print('Files:', os.listdir('/app'))")
    print(f"Session B files (should be empty): {result_b.stdout.strip()}")

    files_a = list_session_files(session_id)
    files_b = list_session_files(session_b_id)
    print(f"Session A has {len(files_a)} files: {files_a}")
    print(f"Session B has {len(files_b)} files: {files_b}")

    # Phase 7: Read final report
    print("\n[Phase 7] Reading generated report from host...")
    report = read_session_file(session_id, "report.txt")
    print("Report content:")
    print(report.decode("utf-8"))

    # Phase 8: Cleanup
    print("\n[Phase 8] Cleaning up sessions...")
    delete_session_workspace(session_id)
    delete_session_workspace(session_b_id)
    print(f"Deleted session workspaces: {session_id}, {session_b_id}")

    # Phase 9: Workspace Pruning Demo
    print("\n[Phase 9] Demonstrating workspace pruning...")
    print("Creating temporary sessions for pruning demo...")

    # Create a few test sessions
    temp_sessions = []
    for i in range(3):
        temp_sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
        temp_id = temp_sandbox.session_id
        temp_sandbox.execute(f"print('Temporary session {i + 1}')")
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
    print("Demo completed successfully!")
    print("=" * 70)
    print("\nKey Takeaways:")
    print("- Sessions provide isolated workspaces for multi-turn execution")
    print("- Files persist across executions within a session")
    print("- Host can read/write session files directly")
    print("- Each session is isolated from others")
    print("- Workspace pruning enables automated cleanup of stale sessions")
    print("- Dry-run mode allows safe preview before deletion")
    print("=" * 70)


if __name__ == "__main__":
    main()
