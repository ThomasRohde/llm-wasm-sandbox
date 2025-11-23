"""
Text Analysis Examples with sandbox_utils

This module demonstrates text processing and analysis workflows using utilities
from the sandbox_utils library. All operations run within the /app sandbox.

Examples include:
- Log file parsing and analysis
- Text search and replace (grep/sed)
- Word frequency analysis
- File content inspection (head/tail/wc)
"""

from sandbox import RuntimeType, create_sandbox


def demo_log_file_analysis():
    """Example: Parse and analyze log files."""
    print("\n" + "=" * 60)
    print("DEMO: Log File Analysis")
    print("=" * 60)

    code = """
from sandbox_utils import echo, grep, wc, head, tail, mkdir

# Create sample log files
mkdir("/app/logs", parents=True)

# Application log with mixed severity levels
app_log = '''2024-11-20 10:15:23 INFO Server started on port 8080
2024-11-20 10:15:24 INFO Database connection established
2024-11-20 10:16:01 WARNING High memory usage detected: 85%
2024-11-20 10:16:45 ERROR Failed to connect to external API: timeout
2024-11-20 10:17:10 INFO Request processed: GET /api/users
2024-11-20 10:17:11 INFO Request processed: POST /api/data
2024-11-20 10:18:30 ERROR Database query failed: connection lost
2024-11-20 10:18:31 CRITICAL Service unavailable - attempting restart
2024-11-20 10:19:00 INFO Service restarted successfully
2024-11-20 10:19:05 WARNING Rate limit exceeded for IP 192.168.1.100
2024-11-20 10:20:15 INFO Request processed: GET /api/status
2024-11-20 10:21:00 ERROR Invalid authentication token
2024-11-20 10:22:30 INFO Request processed: DELETE /api/cache'''

echo(app_log, "/app/logs/app.log")

# Access log
access_log = '''192.168.1.50 - - [20/Nov/2024:10:15:00] "GET /index.html HTTP/1.1" 200 1024
192.168.1.51 - - [20/Nov/2024:10:15:01] "GET /api/users HTTP/1.1" 200 2048
192.168.1.52 - - [20/Nov/2024:10:15:05] "POST /api/login HTTP/1.1" 401 128
192.168.1.50 - - [20/Nov/2024:10:15:10] "GET /static/style.css HTTP/1.1" 200 512
192.168.1.53 - - [20/Nov/2024:10:15:15] "GET /api/data HTTP/1.1" 500 256
192.168.1.51 - - [20/Nov/2024:10:15:20] "PUT /api/users/123 HTTP/1.1" 200 1536'''

echo(access_log, "/app/logs/access.log")

print("=== LOG FILE STATISTICS ===\\n")

# Count lines in each log
app_stats = wc("/app/logs/app.log")
access_stats = wc("/app/logs/access.log")

print(f"app.log:    {app_stats['lines']:3d} lines, {app_stats['words']:4d} words, {app_stats['chars']:5d} chars")
print(f"access.log: {access_stats['lines']:3d} lines, {access_stats['words']:4d} words, {access_stats['chars']:5d} chars")

# Analyze ERROR messages
print("\\n=== ERROR ANALYSIS ===\\n")
error_matches = grep(r"ERROR", ["/app/logs/app.log"])
print(f"Found {len(error_matches)} ERROR entries:")
for file, line_num, line in error_matches:
    timestamp = line.split()[0:2]
    message = ' '.join(line.split()[3:])
    print(f"  [{' '.join(timestamp)}] {message}")

# Analyze CRITICAL messages
print("\\n=== CRITICAL ISSUES ===\\n")
critical_matches = grep(r"CRITICAL", ["/app/logs/app.log"])
if critical_matches:
    for file, line_num, line in critical_matches:
        print(f"  Line {line_num}: {line.strip()}")
else:
    print("  No critical issues found")

# Analyze WARNING messages
print("\\n=== WARNINGS ===\\n")
warning_matches = grep(r"WARNING", ["/app/logs/app.log"])
print(f"Found {len(warning_matches)} warnings:")
for file, line_num, line in warning_matches:
    message = ' '.join(line.split()[3:])
    print(f"  • {message}")

# Show recent activity (last 3 lines)
print("\\n=== RECENT ACTIVITY (last 3 entries) ===\\n")
recent = tail("/app/logs/app.log", lines=3)
for line in recent:
    print(f"  {line}")

# Analyze HTTP status codes in access log
print("\\n=== HTTP STATUS CODE SUMMARY ===\\n")
access_lines = []
with open("/app/logs/access.log", 'r') as f:
    access_lines = f.readlines()

status_codes = {}
for line in access_lines:
    parts = line.split('"')
    if len(parts) >= 3:
        status = parts[2].strip().split()[0]
        status_codes[status] = status_codes.get(status, 0) + 1

for code in sorted(status_codes.keys()):
    count = status_codes[code]
    status_name = {
        '200': 'OK',
        '401': 'Unauthorized',
        '500': 'Internal Server Error'
    }.get(code, 'Unknown')
    print(f"  {code} ({status_name}): {count} requests")

# Find failed requests (4xx and 5xx)
print("\\n=== FAILED REQUESTS ===\\n")
failed_4xx = grep(r'" 4[0-9]{2} ', ["/app/logs/access.log"])
failed_5xx = grep(r'" 5[0-9]{2} ', ["/app/logs/access.log"])

print(f"Client errors (4xx): {len(failed_4xx)}")
for file, line_num, line in failed_4xx:
    print(f"  {line.strip()}")

print(f"\\nServer errors (5xx): {len(failed_5xx)}")
for file, line_num, line in failed_5xx:
    print(f"  {line.strip()}")
"""

    sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
    result = sandbox.execute(code)

    print(result.stdout)
    print(f"\n[Fuel consumed: {result.fuel_consumed:,} instructions]")


def demo_text_search_replace():
    """Example: Search and replace text using grep and sed."""
    print("\n" + "=" * 60)
    print("DEMO: Text Search and Replace")
    print("=" * 60)

    code = """
from sandbox_utils import echo, grep, sed, cat, mkdir

# Create configuration files with placeholders
mkdir("/app/config", parents=True)

config_template = '''# Application Configuration
app_name = "MyApp"
environment = "DEVELOPMENT"
debug_mode = true
api_url = "http://localhost:8080"
database_host = "localhost"
database_port = 5432
max_connections = 10
timeout_seconds = 30
log_level = "DEBUG"
'''

echo(config_template, "/app/config/app.conf")

docker_template = '''FROM python:3.11
WORKDIR /app
ENV ENVIRONMENT=DEVELOPMENT
ENV DEBUG_MODE=true
EXPOSE 8080
CMD ["python", "app.py"]
'''

echo(docker_template, "/app/config/Dockerfile")

print("=== ORIGINAL CONFIGURATION ===\\n")
print(cat("/app/config/app.conf"))

# Search for specific patterns
print("\\n=== SEARCH: Find all 'localhost' references ===\\n")
localhost_refs = grep(r"localhost", ["/app/config/app.conf", "/app/config/Dockerfile"])
for file, line_num, line in localhost_refs:
    print(f"  {file.split('/')[-1]}:{line_num}: {line.strip()}")

# Search for environment settings
print("\\n=== SEARCH: Environment settings ===\\n")
env_settings = grep(r"(?i)(environment|debug)", ["/app/config/app.conf", "/app/config/Dockerfile"])
for file, line_num, line in env_settings:
    print(f"  {line.strip()}")

# Replace DEVELOPMENT with PRODUCTION
print("\\n=== REPLACE: DEVELOPMENT → PRODUCTION ===\\n")
config_content = cat("/app/config/app.conf")
updated_config = sed(r"DEVELOPMENT", "PRODUCTION", config_content)
echo(updated_config, "/app/config/app.conf")
print("✓ Updated app.conf")

docker_content = cat("/app/config/Dockerfile")
updated_docker = sed(r"DEVELOPMENT", "PRODUCTION", docker_content)
echo(updated_docker, "/app/config/Dockerfile")
print("✓ Updated Dockerfile")

# Replace debug mode
print("\\n=== REPLACE: Debug mode ===\\n")
config_content = cat("/app/config/app.conf")
updated_config = sed(r"debug_mode = true", "debug_mode = false", config_content)
echo(updated_config, "/app/config/app.conf")
print("✓ Disabled debug mode in app.conf")

docker_content = cat("/app/config/Dockerfile")
updated_docker = sed(r"DEBUG_MODE=true", "DEBUG_MODE=false", docker_content)
echo(updated_docker, "/app/config/Dockerfile")
print("✓ Disabled debug mode in Dockerfile")

# Replace localhost with production host
print("\\n=== REPLACE: localhost → prod.example.com ===\\n")
config_content = cat("/app/config/app.conf")
updated_config = sed(r"localhost", "prod.example.com", config_content)
echo(updated_config, "/app/config/app.conf")
print("✓ Updated hostnames")

print("\\n=== UPDATED CONFIGURATION ===\\n")
print(cat("/app/config/app.conf"))

# Verify changes
print("\\n=== VERIFICATION: Check for remaining DEVELOPMENT references ===\\n")
dev_refs = grep(r"DEVELOPMENT", ["/app/config/app.conf", "/app/config/Dockerfile"])
if not dev_refs:
    print("✓ No DEVELOPMENT references found - migration complete")
else:
    print(f"⚠ Found {len(dev_refs)} remaining DEVELOPMENT references")
    for file, line_num, line in dev_refs:
        print(f"  {file}:{line_num}: {line.strip()}")
"""

    sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
    result = sandbox.execute(code)

    print(result.stdout)
    print(f"\n[Fuel consumed: {result.fuel_consumed:,} instructions]")


def demo_word_frequency_analysis():
    """Example: Analyze word frequency in text files."""
    print("\n" + "=" * 60)
    print("DEMO: Word Frequency Analysis")
    print("=" * 60)

    code = """
from sandbox_utils import echo, cat, mkdir
import re
from collections import Counter

# Create sample text files
mkdir("/app/texts", parents=True)

article = '''The Python programming language has become one of the most popular programming
languages in the world. Python is known for its simplicity and readability. Many developers
choose Python for web development, data analysis, and machine learning. The Python community
is large and active, providing excellent support and resources. Python's versatility makes
it suitable for beginners and experts alike. Whether you're building web applications or
analyzing data, Python has the tools you need.'''

echo(article, "/app/texts/article.txt")

documentation = '''WASM (WebAssembly) provides a secure sandbox environment for executing code.
The sandbox isolates untrusted code from the host system. Security is paramount when running
code generated by AI models. The WASM sandbox enforces strict security boundaries through
capability-based access control. This security model ensures that sandboxed code cannot
access resources outside its designated workspace.'''

echo(documentation, "/app/texts/docs.txt")

print("=== WORD FREQUENCY ANALYSIS ===\\n")

# Analyze article
article_text = cat("/app/texts/article.txt")
words = re.findall(r'\\b[a-zA-Z]+\\b', article_text.lower())
word_freq = Counter(words)

print("Top 10 words in article.txt:")
for word, count in word_freq.most_common(10):
    print(f"  {word:15s}: {count:2d} occurrences")

# Analyze documentation
print("\\nTop 10 words in docs.txt:")
docs_text = cat("/app/texts/docs.txt")
docs_words = re.findall(r'\\b[a-zA-Z]+\\b', docs_text.lower())
docs_freq = Counter(docs_words)

for word, count in docs_freq.most_common(10):
    print(f"  {word:15s}: {count:2d} occurrences")

# Combined analysis
print("\\n=== COMBINED ANALYSIS ===\\n")
all_words = words + docs_words
combined_freq = Counter(all_words)

print(f"Total unique words: {len(combined_freq)}")
print(f"Total word count: {len(all_words)}")
print(f"Average word length: {sum(len(w) for w in all_words) / len(all_words):.1f} characters")

# Find words appearing in both texts
article_words = set(words)
docs_words_set = set(docs_words)
common_words = article_words & docs_words_set

print(f"\\nWords appearing in both texts: {len(common_words)}")
common_freq = {w: combined_freq[w] for w in common_words if combined_freq[w] > 1}
print("\\nMost common shared words:")
for word, count in sorted(common_freq.items(), key=lambda x: x[1], reverse=True)[:5]:
    print(f"  {word:15s}: {count:2d} total occurrences")

# Find long words (technical terms)
print("\\nLong words (8+ characters):")
long_words = [w for w in combined_freq.keys() if len(w) >= 8]
for word in sorted(long_words)[:10]:
    print(f"  {word} ({combined_freq[word]}x)")
"""

    sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
    result = sandbox.execute(code)

    print(result.stdout)
    print(f"\n[Fuel consumed: {result.fuel_consumed:,} instructions]")


def demo_file_comparison():
    """Example: Compare file contents and show differences."""
    print("\n" + "=" * 60)
    print("DEMO: File Comparison")
    print("=" * 60)

    code = """
from sandbox_utils import echo, diff, mkdir

# Create two versions of a configuration file
mkdir("/app/versions", parents=True)

version1 = '''app_name = "MyApp"
version = "1.0.0"
port = 8080
host = "localhost"
debug = true
max_connections = 100
timeout = 30
cache_enabled = false
'''

version2 = '''app_name = "MyApp"
version = "1.1.0"
port = 8080
host = "0.0.0.0"
debug = false
max_connections = 200
timeout = 60
cache_enabled = true
feature_flags = ["new_ui", "api_v2"]
'''

echo(version1, "/app/versions/config_v1.txt")
echo(version2, "/app/versions/config_v2.txt")

print("=== CONFIGURATION COMPARISON ===\\n")
print("Comparing config_v1.txt (old) vs config_v2.txt (new)\\n")

# Show diff
diff_result = diff("/app/versions/config_v1.txt", "/app/versions/config_v2.txt")
print(diff_result)

# Analyze changes
lines_v1 = version1.strip().split('\\n')
lines_v2 = version2.strip().split('\\n')

print("\\n=== CHANGE SUMMARY ===\\n")
print(f"Old version: {len(lines_v1)} lines")
print(f"New version: {len(lines_v2)} lines")
print(f"Lines added: {len(lines_v2) - len(lines_v1)}")

# Find specific changes
print("\\nKey changes:")
if "version = \\"1.1.0\\"" in version2:
    print("  • Version bumped to 1.1.0")
if "host = \\"0.0.0.0\\"" in version2:
    print("  • Host changed from localhost to 0.0.0.0 (bind all interfaces)")
if "debug = false" in version2:
    print("  • Debug mode disabled")
if "max_connections = 200" in version2:
    print("  • Max connections increased to 200")
if "cache_enabled = true" in version2:
    print("  • Cache enabled")
if "feature_flags" in version2:
    print("  • Feature flags added")
"""

    sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
    result = sandbox.execute(code)

    print(result.stdout)
    print(f"\n[Fuel consumed: {result.fuel_consumed:,} instructions]")


def main():
    """Run all text analysis examples."""
    print("\n" + "=" * 60)
    print("TEXT ANALYSIS EXAMPLES")
    print("Demonstrating sandbox_utils text processing utilities")
    print("=" * 60)

    demo_log_file_analysis()
    demo_text_search_replace()
    demo_word_frequency_analysis()
    demo_file_comparison()

    print("\n" + "=" * 60)
    print("✓ All text analysis examples completed")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
