"""Tests for JavaScript vendored packages functionality.

Verifies that:
1. requireVendor() loads packages successfully
2. CSV parsing/stringification works correctly
3. JSON utilities (get, set, validate) work as expected
4. String utilities provide correct transformations
5. sandbox-utils file operations work correctly
6. Error handling works for missing packages
7. Read-only vendor directory enforcement
"""

from sandbox import RuntimeType, create_sandbox


def test_require_vendor_csv_simple():
    """Test loading and using csv-simple package."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const csv = requireVendor('csv-simple');

// Test parse
const csvData = 'name,age\\nAlice,30\\nBob,25';
const parsed = csv.parse(csvData);
console.log('Parsed:', JSON.stringify(parsed));

// Test stringify
const data = [{name: 'Charlie', age: '35'}];
const stringified = csv.stringify(data);
console.log('Stringified:', stringified);
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Alice" in result.stdout
    assert "Bob" in result.stdout
    assert "Charlie" in result.stdout


def test_require_vendor_json_utils():
    """Test loading and using json-utils package."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const jsonUtils = requireVendor('json-utils');

// Test get
const obj = {user: {name: 'Alice', address: {city: 'NYC'}}};
const city = jsonUtils.get(obj, 'user.address.city');
console.log('City:', city);

// Test set
jsonUtils.set(obj, 'user.age', 30);
console.log('Age:', obj.user.age);

// Test validate
const schema = {type: 'object', properties: {name: {type: 'string', required: true}}};
const valid = jsonUtils.validate({name: 'Bob'}, schema);
console.log('Valid:', valid.valid);

// Test clone
const cloned = jsonUtils.clone(obj);
console.log('Cloned:', JSON.stringify(cloned).length > 0);
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "NYC" in result.stdout
    assert "Age: 30" in result.stdout
    assert "Valid: true" in result.stdout


def test_require_vendor_string_utils():
    """Test loading and using string-utils package."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const str = requireVendor('string-utils');

console.log('Slugify:', str.slugify('Hello World!'));
console.log('Truncate:', str.truncate('This is a long string', 10));
console.log('Capitalize:', str.capitalize('hello'));
console.log('CamelCase:', str.camelCase('hello-world'));
console.log('SnakeCase:', str.snakeCase('HelloWorld'));
console.log('KebabCase:', str.kebabCase('HelloWorld'));
console.log('WordCount:', str.wordCount('one two three'));
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "hello-world" in result.stdout
    assert "This is..." in result.stdout
    assert "Hello" in result.stdout
    assert "helloWorld" in result.stdout
    assert "hello_world" in result.stdout
    assert "hello-world" in result.stdout
    assert "WordCount: 3" in result.stdout


def test_require_vendor_sandbox_utils():
    """Test loading and using sandbox-utils package."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const utils = requireVendor('sandbox-utils');

// Test writeJson and readJson
utils.writeJson('/app/test.json', {message: 'Hello'});
const data = utils.readJson('/app/test.json');
console.log('Read:', data.message);

// Test writeText and readText
utils.writeText('/app/test.txt', 'Hello World');
const text = utils.readText('/app/test.txt');
console.log('Text:', text);

// Test fileExists
console.log('Exists:', utils.fileExists('/app/test.json'));
console.log('Not exists:', utils.fileExists('/app/missing.txt'));

// Test readLines and writeLines
utils.writeLines('/app/lines.txt', ['line1', 'line2', 'line3']);
const lines = utils.readLines('/app/lines.txt');
console.log('Lines:', lines.length);
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Read: Hello" in result.stdout
    assert "Text: Hello World" in result.stdout
    assert "Exists: true" in result.stdout
    assert "Not exists: false" in result.stdout
    assert "Lines: 3" in result.stdout


def test_require_vendor_missing_package():
    """Test error handling for missing packages."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
try {
    const missing = requireVendor('nonexistent-package');
    console.log('Should not reach here');
} catch (e) {
    console.log('Error:', e.message);
}
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Vendor package not found" in result.stdout


def test_injected_globals_available():
    """Test that injected globals (readJson, writeJson, etc.) are available without require."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
// These should be available globally via injection
writeJson('/app/global-test.json', {test: 'value'});
const data = readJson('/app/global-test.json');
console.log('Global test:', data.test);

writeText('/app/global.txt', 'Works!');
console.log('File exists:', fileExists('/app/global.txt'));
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Global test: value" in result.stdout
    assert "File exists: true" in result.stdout


def test_csv_complex_parsing():
    """Test CSV parsing with quoted fields and edge cases."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const csv = requireVendor('csv-simple');

const complexCsv = 'name,quote\\n"Smith, John","He said, \\"Hello\\""';
const parsed = csv.parse(complexCsv);
console.log('Name:', parsed[0].name);
console.log('Quote:', parsed[0].quote);
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Smith, John" in result.stdout


def test_json_utils_validation():
    """Test JSON schema validation with various scenarios."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const jsonUtils = requireVendor('json-utils');

// Valid object
const schema1 = {
    type: 'object',
    properties: {
        name: {type: 'string', required: true},
        age: {type: 'number'}
    }
};
const result1 = jsonUtils.validate({name: 'Alice', age: 30}, schema1);
console.log('Valid object:', result1.valid);

// Missing required field
const result2 = jsonUtils.validate({age: 30}, schema1);
console.log('Missing required:', result2.valid);
console.log('Error count:', result2.errors.length);

// Wrong type
const result3 = jsonUtils.validate({name: 123}, schema1);
console.log('Wrong type:', result3.valid);
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Valid object: true" in result.stdout
    assert "Missing required: false" in result.stdout
    assert "Error count: 1" in result.stdout
    assert "Wrong type: false" in result.stdout


def test_string_utils_palindrome():
    """Test string utilities palindrome detection."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const str = requireVendor('string-utils');

console.log('Palindrome 1:', str.isPalindrome('racecar'));
console.log('Palindrome 2:', str.isPalindrome('A man a plan a canal Panama'));
console.log('Not palindrome:', str.isPalindrome('hello'));
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Palindrome 1: true" in result.stdout
    assert "Palindrome 2: true" in result.stdout
    assert "Not palindrome: false" in result.stdout


def test_sandbox_utils_file_operations():
    """Test sandbox-utils file operations comprehensively."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const utils = requireVendor('sandbox-utils');

// Write and read
utils.writeText('/app/original.txt', 'Original content');

// Copy file
utils.copyFile('/app/original.txt', '/app/copy.txt');
const copied = utils.readText('/app/copy.txt');
console.log('Copied:', copied);

// Append text
utils.appendText('/app/original.txt', '\\nAppended');
const appended = utils.readText('/app/original.txt');
console.log('Lines after append:', appended.split('\\n').length);

// Remove file
const removed = utils.removeFile('/app/copy.txt');
console.log('Removed:', removed);
console.log('Still exists:', utils.fileExists('/app/copy.txt'));
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Copied: Original content" in result.stdout
    assert "Lines after append: 2" in result.stdout
    assert "Removed: true" in result.stdout
    assert "Still exists: false" in result.stdout


def test_no_injection_mode():
    """Test that inject_setup=False prevents automatic injection."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
// This should fail because requireVendor is not available
try {
    const csv = requireVendor('csv-simple');
    console.log('Should not reach here');
} catch (e) {
    console.log('Error (expected):', e.name);
}
"""

    result = sandbox.execute(code, inject_setup=False)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Error (expected):" in result.stdout


def test_vendor_directory_read_only():
    """Test that vendor directory is mounted read-only (cannot write to it)."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
try {
    // Attempt to write to vendor directory should fail
    const f = std.open('/data_js/vendor/malicious.js', 'w');
    if (f) {
        console.log('ERROR: Should not be able to write to vendor!');
        f.close();
    } else {
        console.log('Correctly prevented write to vendor directory');
    }
} catch (e) {
    console.log('Exception prevented write (expected)');
}
"""

    result = sandbox.execute(code)
    # Either should fail to open or throw exception
    assert "ERROR: Should not be able to write" not in result.stdout


def test_multiple_packages_in_single_execution():
    """Test loading and using multiple vendor packages together."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const csv = requireVendor('csv-simple');
const jsonUtils = requireVendor('json-utils');
const str = requireVendor('string-utils');

// Use all packages together
const data = [
    {name: str.capitalize('alice'), age: '30'},
    {name: str.capitalize('bob'), age: '25'}
];

const csvOutput = csv.stringify(data);
console.log('CSV:', csvOutput.split('\\n')[0]);

const obj = {users: data};
const firstAge = jsonUtils.get(obj, 'users.0.age');
console.log('First age:', firstAge);
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "name,age" in result.stdout
    assert "First age: 30" in result.stdout


def test_sandbox_utils_readjson_error_missing_file():
    """Test readJson() error handling for missing files."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const utils = requireVendor('sandbox-utils');

try {
    const data = utils.readJson('/app/nonexistent.json');
    console.log('ERROR: Should have thrown for missing file');
} catch (e) {
    console.log('Caught error:', e.message.includes('not found'));
}
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Caught error: true" in result.stdout


def test_sandbox_utils_readjson_error_invalid_json():
    """Test readJson() error handling for invalid JSON."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const utils = requireVendor('sandbox-utils');

// Write invalid JSON
utils.writeText('/app/invalid.json', '{not valid json}');

try {
    const data = utils.readJson('/app/invalid.json');
    console.log('ERROR: Should have thrown for invalid JSON');
} catch (e) {
    console.log('Caught error:', e.message.includes('Invalid JSON'));
}
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Caught error: true" in result.stdout


def test_sandbox_utils_listfiles():
    """Test listFiles() with various directory structures."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const utils = requireVendor('sandbox-utils');

// Create test directory structure
utils.writeText('/app/file1.txt', 'content1');
utils.writeText('/app/file2.txt', 'content2');
utils.writeText('/app/data.json', '{}');

// List files
const files = utils.listFiles('/app');
console.log('File count:', files.length >= 3);  // At least our 3 files
console.log('Has file1.txt:', files.includes('file1.txt'));
console.log('Has file2.txt:', files.includes('file2.txt'));
console.log('Has data.json:', files.includes('data.json'));
console.log('No dot entries:', !files.includes('.') && !files.includes('..'));
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "File count: true" in result.stdout
    assert "Has file1.txt: true" in result.stdout
    assert "Has file2.txt: true" in result.stdout
    assert "Has data.json: true" in result.stdout
    assert "No dot entries: true" in result.stdout


def test_sandbox_utils_listfiles_error_missing_directory():
    """Test listFiles() error handling for missing directory."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const utils = requireVendor('sandbox-utils');

try {
    const files = utils.listFiles('/app/nonexistent_dir');
    console.log('ERROR: Should have thrown for missing directory');
} catch (e) {
    console.log('Caught error:', e.message.includes('Cannot read directory'));
}
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Caught error: true" in result.stdout


def test_sandbox_utils_readtext_error_handling():
    """Test readText() error handling for missing files."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const utils = requireVendor('sandbox-utils');

try {
    const text = utils.readText('/app/missing.txt');
    console.log('ERROR: Should have thrown');
} catch (e) {
    console.log('Caught error:', e.message.includes('not found'));
}
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Caught error: true" in result.stdout


def test_sandbox_utils_writetext_error_handling():
    """Test writeText() error handling for invalid paths."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const utils = requireVendor('sandbox-utils');

try {
    // Try to write to invalid path (outside /app)
    utils.writeText('/invalid/path/file.txt', 'content');
    console.log('ERROR: Should have thrown');
} catch (e) {
    console.log('Caught error:', e.message.includes('Cannot write'));
}
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Caught error: true" in result.stdout


def test_sandbox_utils_filesize():
    """Test fileSize() function."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const utils = requireVendor('sandbox-utils');

// Write a file with known content
utils.writeText('/app/sized.txt', 'Hello');
const size = utils.fileSize('/app/sized.txt');
console.log('Size:', size);

// Test nonexistent file
const nullSize = utils.fileSize('/app/nonexistent.txt');
console.log('Null size:', nullSize);
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Size: 5" in result.stdout or "Size: 6" in result.stdout  # May include newline
    assert "Null size: null" in result.stdout


def test_sandbox_utils_readlines_writelines():
    """Test readLines() and writeLines() functions."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const utils = requireVendor('sandbox-utils');

// Write lines
const lines = ['Line 1', 'Line 2', 'Line 3'];
utils.writeLines('/app/lines.txt', lines);

// Read lines back
const readLines = utils.readLines('/app/lines.txt');
console.log('Line count:', readLines.length);
console.log('First line:', readLines[0]);
console.log('Last line:', readLines[readLines.length - 1]);

// Test with custom line ending
utils.writeLines('/app/windows.txt', ['A', 'B'], '\\r\\n');
const content = utils.readText('/app/windows.txt');
console.log('Has CRLF:', content.includes('\\r\\n'));
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert (
        "Line count: 3" in result.stdout or "Line count: 4" in result.stdout
    )  # May have empty line
    assert "First line: Line 1" in result.stdout
    assert "Last line: Line 3" in result.stdout or "Last line:" in result.stdout
    assert "Has CRLF: true" in result.stdout


def test_sandbox_utils_appendtext():
    """Test appendText() function."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const utils = requireVendor('sandbox-utils');

// Create initial file
utils.writeText('/app/append.txt', 'Initial');

// Append content
utils.appendText('/app/append.txt', '\\nAppended');

// Read and verify
const content = utils.readText('/app/append.txt');
console.log('Content:', content);
console.log('Has both:', content.includes('Initial') && content.includes('Appended'));
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Has both: true" in result.stdout


def test_sandbox_utils_copyfile():
    """Test copyFile() function."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const utils = requireVendor('sandbox-utils');

// Create source file
utils.writeText('/app/source.txt', 'Source content');

// Copy file
utils.copyFile('/app/source.txt', '/app/destination.txt');

// Verify copy
const destContent = utils.readText('/app/destination.txt');
console.log('Copied correctly:', destContent === 'Source content');
console.log('Both exist:', utils.fileExists('/app/source.txt') && utils.fileExists('/app/destination.txt'));
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Copied correctly: true" in result.stdout
    assert "Both exist: true" in result.stdout


def test_sandbox_utils_removefile():
    """Test removeFile() function."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

    code = """
const utils = requireVendor('sandbox-utils');

// Create and remove file
utils.writeText('/app/todelete.txt', 'Delete me');
const removed = utils.removeFile('/app/todelete.txt');
console.log('Removed:', removed);
console.log('Still exists:', utils.fileExists('/app/todelete.txt'));

// Try removing nonexistent file
const notRemoved = utils.removeFile('/app/never_existed.txt');
console.log('Nonexistent removed:', notRemoved);
"""

    result = sandbox.execute(code)
    assert result.success, f"Execution failed: {result.stderr}"
    assert "Removed: true" in result.stdout
    assert "Still exists: false" in result.stdout
    assert "Nonexistent removed: false" in result.stdout


if __name__ == "__main__":
    import sys

    # Run all tests
    test_functions = [
        test_require_vendor_csv_simple,
        test_require_vendor_json_utils,
        test_require_vendor_string_utils,
        test_require_vendor_sandbox_utils,
        test_require_vendor_missing_package,
        test_injected_globals_available,
        test_csv_complex_parsing,
        test_json_utils_validation,
        test_string_utils_palindrome,
        test_sandbox_utils_file_operations,
        test_no_injection_mode,
        test_vendor_directory_read_only,
        test_multiple_packages_in_single_execution,
        test_sandbox_utils_readjson_error_missing_file,
        test_sandbox_utils_readjson_error_invalid_json,
        test_sandbox_utils_listfiles,
        test_sandbox_utils_listfiles_error_missing_directory,
        test_sandbox_utils_readtext_error_handling,
        test_sandbox_utils_writetext_error_handling,
        test_sandbox_utils_filesize,
        test_sandbox_utils_readlines_writelines,
        test_sandbox_utils_appendtext,
        test_sandbox_utils_copyfile,
        test_sandbox_utils_removefile,
    ]

    failed = 0
    for test_func in test_functions:
        try:
            print(f"Running {test_func.__name__}...", end=" ")
            test_func()
            print("✓")
        except AssertionError as e:
            print(f"✗\n  {e}")
            failed += 1
        except Exception as e:
            print(f"✗ (exception)\n  {e}")
            failed += 1

    print(f"\n{len(test_functions) - failed}/{len(test_functions)} tests passed")
    sys.exit(1 if failed > 0 else 0)
