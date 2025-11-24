/**
 * csv-simple.js - RFC 4180 compliant CSV parser and stringifier
 * Pure JavaScript implementation for QuickJS WASM environment
 * 
 * License: MIT
 * Adapted from public domain CSV parsing algorithms
 */

/**
 * Parse CSV string to array of objects
 * @param {string} csv - CSV string to parse
 * @param {object} options - Parsing options
 * @param {string} options.delimiter - Field delimiter (default: ',')
 * @param {string} options.quote - Quote character (default: '"')
 * @param {boolean} options.headers - Use first row as headers (default: true)
 * @returns {Array<object>|Array<Array<string>>} Parsed data
 */
function parse(csv, options = {}) {
    const delimiter = options.delimiter || ',';
    const quote = options.quote || '"';
    const useHeaders = options.headers !== false;
    
    const rows = [];
    let currentRow = [];
    let currentField = '';
    let inQuotes = false;
    
    for (let i = 0; i < csv.length; i++) {
        const char = csv[i];
        const nextChar = csv[i + 1];
        
        if (char === quote) {
            if (inQuotes && nextChar === quote) {
                // Escaped quote
                currentField += quote;
                i++;
            } else {
                // Toggle quote mode
                inQuotes = !inQuotes;
            }
        } else if (char === delimiter && !inQuotes) {
            // End of field
            currentRow.push(currentField);
            currentField = '';
        } else if ((char === '\n' || char === '\r') && !inQuotes) {
            // End of row
            if (char === '\r' && nextChar === '\n') {
                i++; // Skip \n in \r\n
            }
            if (currentField || currentRow.length > 0) {
                currentRow.push(currentField);
                rows.push(currentRow);
                currentRow = [];
                currentField = '';
            }
        } else {
            currentField += char;
        }
    }
    
    // Handle last field/row
    if (currentField || currentRow.length > 0) {
        currentRow.push(currentField);
        rows.push(currentRow);
    }
    
    // Convert to objects if headers enabled
    if (useHeaders && rows.length > 0) {
        const headers = rows[0];
        return rows.slice(1).map(row => {
            const obj = {};
            headers.forEach((header, i) => {
                obj[header] = row[i] || '';
            });
            return obj;
        });
    }
    
    return rows;
}

/**
 * Stringify array of objects or arrays to CSV
 * @param {Array<object>|Array<Array>} data - Data to stringify
 * @param {object} options - Stringification options
 * @param {string} options.delimiter - Field delimiter (default: ',')
 * @param {string} options.quote - Quote character (default: '"')
 * @param {Array<string>} options.headers - Custom headers (auto-detected if not provided)
 * @returns {string} CSV string
 */
function stringify(data, options = {}) {
    if (!data || data.length === 0) return '';
    
    const delimiter = options.delimiter || ',';
    const quote = options.quote || '"';
    
    // Determine if data is objects or arrays
    const isObjects = typeof data[0] === 'object' && !Array.isArray(data[0]);
    
    let headers;
    if (options.headers) {
        headers = options.headers;
    } else if (isObjects) {
        headers = Object.keys(data[0]);
    }
    
    const rows = [];
    
    // Add header row if dealing with objects
    if (headers) {
        rows.push(headers.map(h => escapeField(h, delimiter, quote)).join(delimiter));
    }
    
    // Add data rows
    for (const item of data) {
        let row;
        if (isObjects) {
            row = headers.map(h => escapeField(String(item[h] || ''), delimiter, quote));
        } else {
            row = item.map(f => escapeField(String(f), delimiter, quote));
        }
        rows.push(row.join(delimiter));
    }
    
    return rows.join('\n');
}

/**
 * Escape field for CSV output
 * @private
 */
function escapeField(field, delimiter, quote) {
    if (!field) return '';
    
    // Quote field if it contains delimiter, quote, or newline
    if (field.includes(delimiter) || field.includes(quote) || field.includes('\n') || field.includes('\r')) {
        // Escape quotes by doubling them
        const escaped = field.replace(new RegExp(quote, 'g'), quote + quote);
        return quote + escaped + quote;
    }
    
    return field;
}

// CommonJS-style export
module.exports = {
    parse,
    stringify
};
