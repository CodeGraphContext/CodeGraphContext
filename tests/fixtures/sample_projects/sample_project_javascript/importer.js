import defaultExport, { exportedFunction, ExportedClass, exportedVariable as myVar } from './exporter.js';
import * as exporter from './exporter.js';
const { exportedFunction: destructuredFunc } = exporter;

console.log(defaultExport());
console.log(exportedFunction());
const instance = new ExportedClass();
console.log(instance.name);
console.log(myVar);
console.log(exporter.exportedVariable);
console.log(destructuredFunc());
