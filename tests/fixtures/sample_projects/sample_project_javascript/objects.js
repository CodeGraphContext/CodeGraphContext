/**
 * Sample JavaScript file demonstrating object methods and function assignments
 * This file tests methods defined in object literals and prototype assignments
 */

// Object with method definitions
const calculator = {
    result: 0,

    // Method shorthand syntax
    add(value) {
        this.result += value;
        return this;
    },

    // Method shorthand syntax with parameters
    subtract(value) {
        this.result -= value;
        return this;
    },

    // Traditional method definition
    multiply: function(value) {
        this.result *= value;
        return this;
    },

    // Arrow function as method (note: 'this' behaves differently)
    reset: () => {
        // Note: Arrow functions don't have their own 'this'
        console.log('Calculator reset');
    },

    // Method with complex logic
    calculate(operation, value) {
        switch (operation) {
            case 'add':
                return this.add(value);
            case 'subtract':
                return this.subtract(value);
            case 'multiply':
                return this.multiply(value);
            default:
                throw new Error('Unknown operation');
        }
    },

    // Getter method
    get value() {
        return this.result;
    },

    // Setter method
    set value(newValue) {
        this.result = newValue;
    }
};

// Object with nested methods
const api = {
    baseUrl: 'https://api.example.com',
    
    users: {
        // Nested method
        getAll() {
            return fetch(`${this.baseUrl}/users`);
        },

        // Nested method with parameters
        getById(id) {
            return fetch(`${this.baseUrl}/users/${id}`);
        },

        // Async nested method
        async create(userData) {
            const response = await fetch(`${this.baseUrl}/users`, {
                method: 'POST',
                body: JSON.stringify(userData)
            });
            return response.json();
        }
    },

    posts: {
        getAll() {
            return fetch(`${this.baseUrl}/posts`);
        },

        getByUserId(userId) {
            return fetch(`${this.baseUrl}/posts?userId=${userId}`);
        }
    }
};

// Constructor function with prototype methods
function Vehicle(make, model, year) {
    this.make = make;
    this.model = model;
    this.year = year;
}

// Prototype method assignment
Vehicle.prototype.getInfo = function() {
    return `${this.year} ${this.make} ${this.model}`;
};

// Another prototype method
Vehicle.prototype.start = function() {
    console.log(`Starting ${this.getInfo()}`);
};

// Prototype method with parameters
Vehicle.prototype.drive = function(distance) {
    console.log(`Driving ${this.getInfo()} for ${distance} miles`);
};

// Static method assignment to constructor function
Vehicle.createElectric = function(make, model, year, batteryCapacity) {
    const vehicle = new Vehicle(make, model, year);
    vehicle.batteryCapacity = batteryCapacity;
    vehicle.charge = function(percentage) {
        console.log(`Charging to ${percentage}%`);
    };
    return vehicle;
};

// Object with methods that call other methods
const gameEngine = {
    score: 0,
    level: 1,

    // Method that calls other methods
    startGame() {
        this.initializeLevel();
        this.resetScore();
        this.showWelcomeMessage();
    },

    initializeLevel() {
        console.log(`Initializing level ${this.level}`);
    },

    resetScore() {
        this.score = 0;
        console.log('Score reset to 0');
    },

    showWelcomeMessage() {
        console.log('Welcome to the game!');
    },

    // Method with callback parameter
    processInput(input, callback) {
        console.log(`Processing input: ${input}`);
        if (callback && typeof callback === 'function') {
            callback(input);
        }
    },

    // Method that returns a function
    createScoreHandler() {
        return (points) => {
            this.score += points;
            console.log(`Score: ${this.score}`);
        };
    }
};

// Module pattern with private and public methods
const counterModule = (function() {
    let count = 0;

    // Private function
    function validateIncrement(value) {
        return typeof value === 'number' && value > 0;
    }

    // Return public interface
    return {
        // Public method
        increment(value = 1) {
            if (validateIncrement(value)) {
                count += value;
            }
        },

        // Public method
        decrement(value = 1) {
            if (validateIncrement(value)) {
                count -= value;
            }
        },

        // Public getter
        getCount() {
            return count;
        },

        // Public method that uses private function
        reset() {
            count = 0;
            console.log('Counter reset');
        }
    };
})();

// Factory function that creates objects with methods
function createTimer(name) {
    let startTime = null;
    let endTime = null;

    return {
        name: name,

        start() {
            startTime = Date.now();
            console.log(`Timer ${this.name} started`);
        },

        stop() {
            endTime = Date.now();
            console.log(`Timer ${this.name} stopped`);
        },

        getElapsed() {
            if (startTime && endTime) {
                return endTime - startTime;
            }
            return 0;
        },

        reset() {
            startTime = null;
            endTime = null;
            console.log(`Timer ${this.name} reset`);
        }
    };
}

// Function that demonstrates object method usage
function demonstrateObjects() {
    // Use calculator
    calculator.add(10).multiply(2).subtract(5);
    console.log('Calculator result:', calculator.value);

    // Use vehicle
    const car = new Vehicle('Toyota', 'Camry', 2022);
    car.start();
    car.drive(100);

    // Use game engine
    gameEngine.startGame();
    const scoreHandler = gameEngine.createScoreHandler();
    scoreHandler(100);

    // Use counter module
    counterModule.increment(5);
    counterModule.decrement(2);
    console.log('Counter value:', counterModule.getCount());

    // Use timer factory
    const timer = createTimer('TestTimer');
    timer.start();
    setTimeout(() => {
        timer.stop();
        console.log('Elapsed time:', timer.getElapsed());
    }, 1000);

    return {
        calculator,
        car,
        gameEngine,
        counterModule,
        timer
    };
}

// Export objects and functions
export { calculator, api, Vehicle, gameEngine, counterModule, createTimer };
export default demonstrateObjects;