/**
 * The "Polyglot" Blind Spot:
 * Mixed CommonJS (require/exports), ESM (import/export), 
 * and Dynamic Imports in a single file.
 */

// 1. Legacy CommonJS require
const fs = require('fs');
const { calculator } = require('./objects');

// 2. Modern ESM Import (if supported by environment/polyfilled)
import { api } from './objects';

// 3. Re-exporting via both systems
export const version = '1.0.0';
module.exports.legacyVersion = '1.0.0-cjs';

export async function complexAction(path) {
    // 4. Dynamic Import
    const extraUtils = await import('./utils.js');
    
    // Using objects from all three systems
    const data = fs.readFileSync(path, 'utf8');
    const result = calculator.add(data.length).value;
    
    return extraUtils.format(result);
}

// 5. Direct modification of exports object
exports.healthCheck = () => "OK";

/**
 * 6. Conditional Exports (Common in library wrappers)
 */
if (typeof exports === 'object' && typeof module !== 'undefined') {
    module.exports.isNode = true;
} else {
    // browser-specific export
}
