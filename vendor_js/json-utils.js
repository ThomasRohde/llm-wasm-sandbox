/**
 * json-utils.js - JSON path access and schema validation helpers
 * Pure JavaScript implementation for QuickJS WASM environment
 * 
 * License: MIT
 */

/**
 * Get nested property from object using dot notation path
 * @param {object} obj - Object to access
 * @param {string} path - Dot notation path (e.g., 'user.address.city')
 * @param {*} defaultValue - Value to return if path doesn't exist
 * @returns {*} Value at path or defaultValue
 */
function get(obj, path, defaultValue = undefined) {
    if (!obj || typeof obj !== 'object') return defaultValue;
    
    const parts = path.split('.');
    let current = obj;
    
    for (const part of parts) {
        if (current == null || typeof current !== 'object') {
            return defaultValue;
        }
        current = current[part];
    }
    
    return current !== undefined ? current : defaultValue;
}

/**
 * Set nested property in object using dot notation path
 * Creates intermediate objects as needed
 * @param {object} obj - Object to modify
 * @param {string} path - Dot notation path
 * @param {*} value - Value to set
 * @returns {object} Modified object (same reference)
 */
function set(obj, path, value) {
    if (!obj || typeof obj !== 'object') {
        throw new Error('First argument must be an object');
    }
    
    const parts = path.split('.');
    const lastPart = parts.pop();
    let current = obj;
    
    for (const part of parts) {
        if (!(part in current) || typeof current[part] !== 'object') {
            current[part] = {};
        }
        current = current[part];
    }
    
    current[lastPart] = value;
    return obj;
}

/**
 * Simple JSON schema validation
 * Supports basic type checking and required fields
 * @param {*} obj - Object to validate
 * @param {object} schema - Validation schema
 * @returns {object} { valid: boolean, errors: string[] }
 */
function validate(obj, schema) {
    const errors = [];
    
    // Type validation
    if (schema.type) {
        const actualType = Array.isArray(obj) ? 'array' : typeof obj;
        if (actualType !== schema.type) {
            errors.push(`Expected type ${schema.type}, got ${actualType}`);
            return { valid: false, errors };
        }
    }
    
    // Object properties validation
    if (schema.type === 'object' && schema.properties) {
        for (const [key, propSchema] of Object.entries(schema.properties)) {
            const value = obj[key];
            
            // Required field check
            if (propSchema.required && value === undefined) {
                errors.push(`Missing required field: ${key}`);
                continue;
            }
            
            // Type check for property
            if (value !== undefined && propSchema.type) {
                const valueType = Array.isArray(value) ? 'array' : typeof value;
                if (valueType !== propSchema.type) {
                    errors.push(`Field '${key}': expected ${propSchema.type}, got ${valueType}`);
                }
            }
            
            // Enum check
            if (value !== undefined && propSchema.enum) {
                if (!propSchema.enum.includes(value)) {
                    errors.push(`Field '${key}': value '${value}' not in allowed values: ${propSchema.enum.join(', ')}`);
                }
            }
        }
    }
    
    // Array items validation
    if (schema.type === 'array' && schema.items && Array.isArray(obj)) {
        obj.forEach((item, index) => {
            const itemResult = validate(item, schema.items);
            if (!itemResult.valid) {
                errors.push(`Array item ${index}: ${itemResult.errors.join(', ')}`);
            }
        });
    }
    
    return {
        valid: errors.length === 0,
        errors
    };
}

/**
 * Deep clone an object (JSON-serializable objects only)
 * @param {*} obj - Object to clone
 * @returns {*} Deep cloned object
 */
function clone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

/**
 * Deep merge two objects
 * @param {object} target - Target object
 * @param {object} source - Source object
 * @returns {object} Merged object
 */
function merge(target, source) {
    const result = clone(target);
    
    for (const key in source) {
        if (source.hasOwnProperty(key)) {
            if (typeof source[key] === 'object' && !Array.isArray(source[key]) && source[key] !== null) {
                result[key] = merge(result[key] || {}, source[key]);
            } else {
                result[key] = source[key];
            }
        }
    }
    
    return result;
}

// CommonJS-style export
module.exports = {
    get,
    set,
    validate,
    clone,
    merge
};
