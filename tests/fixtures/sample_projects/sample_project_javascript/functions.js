/**
 * Sample JavaScript file demonstrating various function definitions
 * This file tests function declarations, arrow functions, and method definitions
 */

// Regular function declaration
function regularFunction(param1, param2) {
    console.log('Regular function called with:', param1, param2);
    return param1 + param2;
}

/**
 * Function with JSDoc documentation
 * @param {string} name - The name to greet
 * @param {number} age - The age of the person
 * @returns {string} A greeting message
 */
function greetPerson(name, age = 25) {
    return `Hello ${name}, you are ${age} years old!`;
}

// Function expression assigned to variable
const functionExpression = function(x, y) {
    return x * y;
};

// Arrow function with multiple parameters
const arrowFunction = (a, b, c) => {
    const result = a + b + c;
    return result;
};

// Arrow function with single parameter (no parentheses)
const singleParamArrow = x => x * 2;

// Arrow function with no parameters
const noParamsArrow = () => {
    console.log('No parameters arrow function');
    return 42;
};

// Arrow function with rest parameters
const restParamsFunction = (...args) => {
    return args.reduce((sum, val) => sum + val, 0);
};

// Arrow function with destructuring parameters
const destructuringParams = ({name, age}) => {
    return `${name} is ${age} years old`;
};

// Higher-order function
const higherOrderFunction = (callback) => {
    return function(value) {
        return callback(value * 2);
    };
};

// Immediately Invoked Function Expression (IIFE)
const iife = (function() {
    const privateVar = 'secret';
    return function() {
        return privateVar;
    };
})();

// Function with complex parameters
function complexParams(required, optional = 'default', ...rest) {
    console.log('Required:', required);
    console.log('Optional:', optional);
    console.log('Rest:', rest);
}

// Async function
async function asyncFunction(url) {
    try {
        const response = await fetch(url);
        return await response.json();
    } catch (error) {
        console.error('Error:', error);
        throw error;
    }
}

// Async arrow function
const asyncArrowFunction = async (data) => {
    const processed = await processData(data);
    return processed;
};

// Generator function
function* generatorFunction(start, end) {
    for (let i = start; i <= end; i++) {
        yield i;
    }
}

// Function that calls other functions
function orchestrator() {
    const result1 = regularFunction(5, 3);
    const result2 = functionExpression(4, 6);
    const result3 = arrowFunction(1, 2, 3);
    
    return {
        sum: result1,
        product: result2,
        total: result3
    };
}

// Export functions for module usage
export { regularFunction, greetPerson, arrowFunction };
export default orchestrator;