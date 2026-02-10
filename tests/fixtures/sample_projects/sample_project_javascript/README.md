# JavaScript Sample Project

This directory contains comprehensive JavaScript test files to demonstrate and test the enhanced JavaScript support in CodeGraphContext.

## Files Overview

### `functions.js`
Demonstrates various function definition patterns:
- Regular function declarations
- Function expressions
- Arrow functions (with multiple parameters, single parameter, no parameters)
- Functions with default parameters
- Functions with rest parameters
- Functions with destructuring parameters
- Async functions
- Generator functions
- Higher-order functions
- IIFE (Immediately Invoked Function Expressions)

### `classes.js`
Demonstrates class definitions and inheritance:
- Basic class declarations
- Constructor methods
- Instance methods
- Static methods
- Getter and setter methods
- Class inheritance with `extends`
- Method overriding
- Private fields and methods (modern JavaScript)
- Class expressions
- Mixin patterns

### `objects.js`
Demonstrates object methods and prototype assignments:
- Object literal methods (shorthand and traditional syntax)
- Nested object methods
- Prototype method assignments
- Constructor functions with prototype methods
- Module pattern with private/public methods
- Factory functions that create objects with methods
- Methods that call other methods
- Callback and higher-order function patterns

## Expected Function Detections

The enhanced JavaScript parser should detect and properly index:

1. **Function Declarations**: `function functionName(params) { ... }`
2. **Function Expressions**: `const func = function(params) { ... }`
3. **Arrow Functions**: `const func = (params) => { ... }`
4. **Single Parameter Arrow**: `const func = param => { ... }`
5. **Method Definitions**: `methodName(params) { ... }` in classes and objects
6. **Static Methods**: `static methodName(params) { ... }`
7. **Prototype Methods**: `Constructor.prototype.method = function(params) { ... }`
8. **Getter/Setter Methods**: `get property() { ... }` and `set property(value) { ... }`

## Testing Instructions

1. Index this JavaScript sample project using CodeGraphContext
2. Verify that all function types are detected with correct:
   - Function names
   - Line numbers
   - Parameter lists
   - File paths
   - JSDoc comments (where applicable)

## Expected Neo4j Query Results

After indexing, you should be able to run queries like:

```cypher
// Find all JavaScript functions
MATCH (f:Function) 
WHERE f.lang = 'javascript'
RETURN f.name, f.line_number, f.path, f.args

// Find all JavaScript classes
MATCH (c:Class) 
WHERE c.lang = 'javascript'
RETURN c.name, c.line_number, c.path

// Find function call relationships
MATCH (caller:Function)-[r:CALLS]->(callee:Function) 
WHERE caller.lang = 'javascript'
RETURN caller.name + " → " + callee.name as CallChain
```