"""Fix test_session_lifecycle.py to add session_id assignments after create_sandbox calls."""

from pathlib import Path

file_path = Path("tests/test_session_lifecycle.py")
content = file_path.read_text()

# Add session_id = sandbox.session_id after multi-line create_sandbox calls
# Pattern: Look for lines with create_sandbox followed by closing paren
lines = content.split("\n")
new_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    new_lines.append(line)

    # Check if this is a create_sandbox call
    if "= create_sandbox(" in line:
        # Find the closing paren
        if ")" not in line:
            # Multi-line call
            i += 1
            while i < len(lines):
                new_lines.append(lines[i])
                if ")" in lines[i]:
                    break
                i += 1

        # Add session_id assignment after the call
        indent = len(line) - len(line.lstrip())
        new_lines.append(" " * indent + "session_id = sandbox.session_id")

    i += 1

content = "\n".join(new_lines)
file_path.write_text(content)
print("Updated test_session_lifecycle.py with session_id assignments")
