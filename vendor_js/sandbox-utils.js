/**
 * sandbox-utils.js - LLM-friendly file and data helpers
 * Pure JavaScript implementation for QuickJS WASM environment
 * Provides shell-like APIs optimized for LLM code generation
 * 
 * License: MIT
 * 
 * NOTE: Requires QuickJS std module to be available
 * Usage: import * as std from "std";
 */

/**
 * Read and parse JSON file
 * @param {string} path - Path to JSON file (relative to /app)
 * @returns {*} Parsed JSON data
 * @throws {Error} If file doesn't exist or contains invalid JSON
 */
function readJson(path) {
    const f = std.open(path, 'r');
    if (!f) {
        throw new Error(`File not found: ${path}`);
    }
    
    const content = f.readAsString();
    f.close();
    
    try {
        return JSON.parse(content);
    } catch (e) {
        throw new Error(`Invalid JSON in ${path}: ${e.message}`);
    }
}

/**
 * Stringify and write JSON file
 * @param {string} path - Path to JSON file (relative to /app)
 * @param {*} obj - Object to serialize
 * @param {number} indent - Indentation spaces (default: 2)
 * @throws {Error} If file cannot be written
 */
function writeJson(path, obj, indent = 2) {
    const json = JSON.stringify(obj, null, indent);
    
    const f = std.open(path, 'w');
    if (!f) {
        throw new Error(`Cannot write file: ${path}`);
    }
    
    f.puts(json);
    f.close();
}

/**
 * Read text file content
 * @param {string} path - Path to text file (relative to /app)
 * @returns {string} File content
 * @throws {Error} If file doesn't exist
 */
function readText(path) {
    const f = std.open(path, 'r');
    if (!f) {
        throw new Error(`File not found: ${path}`);
    }
    
    const content = f.readAsString();
    f.close();
    
    return content;
}

/**
 * Write text file
 * @param {string} path - Path to text file (relative to /app)
 * @param {string} content - Content to write
 * @throws {Error} If file cannot be written
 */
function writeText(path, content) {
    const f = std.open(path, 'w');
    if (!f) {
        throw new Error(`Cannot write file: ${path}`);
    }
    
    f.puts(content);
    f.close();
}

/**
 * Check if file exists
 * @param {string} path - Path to file (relative to /app)
 * @returns {boolean} True if file exists
 */
function fileExists(path) {
    const f = std.open(path, 'r');
    if (f) {
        f.close();
        return true;
    }
    return false;
}

/**
 * Read file as lines
 * @param {string} path - Path to text file (relative to /app)
 * @returns {string[]} Array of lines (without newline characters)
 * @throws {Error} If file doesn't exist
 */
function readLines(path) {
    const content = readText(path);
    return content.split(/\r?\n/);
}

/**
 * Write lines to file
 * @param {string} path - Path to text file (relative to /app)
 * @param {string[]} lines - Array of lines to write
 * @param {string} lineEnding - Line ending to use (default: '\n')
 * @throws {Error} If file cannot be written
 */
function writeLines(path, lines, lineEnding = '\n') {
    const content = lines.join(lineEnding);
    writeText(path, content);
}

/**
 * Append text to file
 * @param {string} path - Path to text file (relative to /app)
 * @param {string} content - Content to append
 * @throws {Error} If file cannot be written
 */
function appendText(path, content) {
    const f = std.open(path, 'a');
    if (!f) {
        throw new Error(`Cannot write file: ${path}`);
    }
    
    f.puts(content);
    f.close();
}

/**
 * Get file size in bytes
 * @param {string} path - Path to file (relative to /app)
 * @returns {number|null} File size in bytes, or null if file doesn't exist
 */
function fileSize(path) {
    try {
        // os.stat returns [stat_object, errno] tuple
        const result = os.stat(path);
        if (!result || !Array.isArray(result)) {
            return null;
        }
        
        const [stat, errno] = result;
        
        if (errno !== 0 || !stat) {
            return null;
        }
        
        return stat.size;
    } catch (e) {
        return null;
    }
}

/**
 * List files in directory
 * @param {string} path - Directory path (relative to /app)
 * @returns {string[]} Array of filenames (not full paths)
 * @throws {Error} If directory doesn't exist or cannot be read
 */
function listFiles(path) {
    try {
        // os.readdir returns [array, errno] tuple
        const result = os.readdir(path);
        if (!result || !Array.isArray(result)) {
            throw new Error(`Cannot read directory: ${path}`);
        }
        
        const [entries, errno] = result;
        
        if (errno !== 0) {
            throw new Error(`Cannot read directory ${path}: error code ${errno}`);
        }
        
        if (!entries || !Array.isArray(entries)) {
            throw new Error(`Cannot read directory: ${path}`);
        }
        
        // Filter out '.' and '..'
        return entries.filter(name => name !== '.' && name !== '..');
    } catch (e) {
        throw new Error(`Cannot read directory ${path}: ${e.message}`);
    }
}

/**
 * Copy file
 * @param {string} src - Source file path
 * @param {string} dest - Destination file path
 * @throws {Error} If source doesn't exist or copy fails
 */
function copyFile(src, dest) {
    const content = readText(src);
    writeText(dest, content);
}

/**
 * Remove file
 * @param {string} path - File path to remove
 * @returns {boolean} True if file was removed, false if file didn't exist
 * @throws {Error} If removal fails for reasons other than file not existing
 */
function removeFile(path) {
    // os.remove returns errno (0 = success, negative = error)
    const errno = os.remove(path);
    
    if (errno === 0) {
        return true;
    }
    
    // Check if error is because file doesn't exist
    // errno -44 is ENOENT (No such file or directory)
    if (errno === -44) {
        return false;
    }
    
    // Other errors should throw
    throw new Error(`Cannot remove file ${path}: error code ${errno}`);
}

// CommonJS-style export
module.exports = {
    readJson,
    writeJson,
    readText,
    writeText,
    fileExists,
    readLines,
    writeLines,
    appendText,
    fileSize,
    listFiles,
    copyFile,
    removeFile
};
