/**
 * Tough Case: Mixed CommonJS and ESM
 * Some parsers choke when they see both 'require' and 'export' in the same project
 * or even the same file (though illegal in strict ESM, common in polyfilled environments).
 */

// CommonJS require
const { calculator } = require('./objects');

/**
 * Tough Case: Export Loop
 * Circular re-exports.
 */
export { calculator as Calc };
export * from './importer'; // importer.js might import this file back

export function mixedAction(val) {
    return calculator.add(val).value;
}

// Dynamic property assignment
module.exports.dynamicExport = (x) => x * 2;
