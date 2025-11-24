/**
 * string-utils.js - Common string manipulation functions
 * Pure JavaScript implementation for QuickJS WASM environment
 * 
 * License: MIT
 */

/**
 * Convert string to URL-friendly slug
 * @param {string} text - Text to slugify
 * @param {string} separator - Word separator (default: '-')
 * @returns {string} Slugified text
 */
function slugify(text, separator = '-') {
    return text
        .toString()
        .toLowerCase()
        .trim()
        .replace(/\s+/g, separator)           // Replace spaces with separator
        .replace(/[^\w\-]+/g, '')             // Remove non-word chars
        .replace(/\-\-+/g, separator)         // Replace multiple separators with single
        .replace(/^-+/, '')                   // Trim separator from start
        .replace(/-+$/, '');                  // Trim separator from end
}

/**
 * Truncate string to specified length with suffix
 * @param {string} text - Text to truncate
 * @param {number} length - Maximum length
 * @param {string} suffix - Suffix to add (default: '...')
 * @returns {string} Truncated text
 */
function truncate(text, length, suffix = '...') {
    if (text.length <= length) return text;
    return text.substring(0, length - suffix.length) + suffix;
}

/**
 * Capitalize first letter of string
 * @param {string} text - Text to capitalize
 * @returns {string} Capitalized text
 */
function capitalize(text) {
    if (!text) return text;
    return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * Convert string to camelCase
 * @param {string} text - Text to convert
 * @returns {string} camelCase text
 */
function camelCase(text) {
    return text
        .toLowerCase()
        .replace(/[^a-zA-Z0-9]+(.)/g, (_, char) => char.toUpperCase());
}

/**
 * Convert string to snake_case
 * @param {string} text - Text to convert
 * @returns {string} snake_case text
 */
function snakeCase(text) {
    return text
        .replace(/([A-Z])/g, '_$1')
        .replace(/[^a-zA-Z0-9]+/g, '_')
        .toLowerCase()
        .replace(/^_+|_+$/g, '');
}

/**
 * Convert string to kebab-case
 * @param {string} text - Text to convert
 * @returns {string} kebab-case text
 */
function kebabCase(text) {
    return text
        .replace(/([A-Z])/g, '-$1')
        .replace(/[^a-zA-Z0-9]+/g, '-')
        .toLowerCase()
        .replace(/^-+|-+$/g, '');
}

/**
 * Pad string to specified length
 * @param {string} text - Text to pad
 * @param {number} length - Target length
 * @param {string} char - Padding character (default: ' ')
 * @param {string} direction - 'left', 'right', or 'both' (default: 'right')
 * @returns {string} Padded text
 */
function pad(text, length, char = ' ', direction = 'right') {
    const str = String(text);
    if (str.length >= length) return str;
    
    const padLength = length - str.length;
    const padStr = char.repeat(padLength);
    
    if (direction === 'left') {
        return padStr + str;
    } else if (direction === 'both') {
        const leftPad = Math.floor(padLength / 2);
        const rightPad = padLength - leftPad;
        return char.repeat(leftPad) + str + char.repeat(rightPad);
    } else {
        return str + padStr;
    }
}

/**
 * Remove leading and trailing whitespace, normalize internal whitespace
 * @param {string} text - Text to clean
 * @returns {string} Cleaned text
 */
function clean(text) {
    return text.trim().replace(/\s+/g, ' ');
}

/**
 * Count occurrences of substring in string
 * @param {string} text - Text to search
 * @param {string} substring - Substring to count
 * @param {boolean} caseSensitive - Case sensitive search (default: true)
 * @returns {number} Occurrence count
 */
function count(text, substring, caseSensitive = true) {
    if (!substring) return 0;
    
    const searchText = caseSensitive ? text : text.toLowerCase();
    const searchSubstring = caseSensitive ? substring : substring.toLowerCase();
    
    let count = 0;
    let pos = 0;
    
    while ((pos = searchText.indexOf(searchSubstring, pos)) !== -1) {
        count++;
        pos += searchSubstring.length;
    }
    
    return count;
}

/**
 * Reverse string
 * @param {string} text - Text to reverse
 * @returns {string} Reversed text
 */
function reverse(text) {
    return text.split('').reverse().join('');
}

/**
 * Check if string is palindrome
 * @param {string} text - Text to check
 * @param {boolean} ignoreCase - Ignore case (default: true)
 * @param {boolean} ignoreSpaces - Ignore spaces (default: true)
 * @returns {boolean} True if palindrome
 */
function isPalindrome(text, ignoreCase = true, ignoreSpaces = true) {
    let processed = text;
    if (ignoreSpaces) processed = processed.replace(/\s+/g, '');
    if (ignoreCase) processed = processed.toLowerCase();
    
    return processed === reverse(processed);
}

/**
 * Extract all words from text
 * @param {string} text - Text to extract words from
 * @returns {string[]} Array of words
 */
function words(text) {
    return text.match(/\b\w+\b/g) || [];
}

/**
 * Word count
 * @param {string} text - Text to count words in
 * @returns {number} Word count
 */
function wordCount(text) {
    return words(text).length;
}

// CommonJS-style export
module.exports = {
    slugify,
    truncate,
    capitalize,
    camelCase,
    snakeCase,
    kebabCase,
    pad,
    clean,
    count,
    reverse,
    isPalindrome,
    words,
    wordCount
};
