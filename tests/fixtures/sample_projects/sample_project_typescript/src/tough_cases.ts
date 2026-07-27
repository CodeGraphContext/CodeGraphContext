/**
 * Tough Case 1: Circular Dependencies
 * file_a.ts and file_b.ts import each other.
 */
import { ClassB } from './tough_circular_b';

export class ClassA {
    constructor(private b: ClassB) {}
    
    execute() {
        console.log("ClassA executing");
        this.b.respond();
    }

    ping() {
        console.log("ClassA pinged");
    }
}

/**
 * Tough Case 2: Deep Re-export Chains
 * index.ts -> reexports.ts -> specific.ts
 */
export * from './tough_reexports';

/**
 * Tough Case 3: Dynamic Imports with Variables
 */
export async function loadModuleDynamically(moduleName: string) {
    // Variable path in dynamic import
    const module = await import(`./tough_dynamic_${moduleName}`);
    return module.default();
}

/**
 * Tough Case 4: Shadowing and Closures
 */
export function createNestedState(initial: number) {
    const value = initial;
    
    return (increment: number) => {
        const value = initial + increment; // Shadowing
        
        return (multiplier: number) => {
            const value = (initial + increment) * multiplier; // Shadowing again
            return value;
        };
    };
}

/**
 * Tough Case 5: Complex Mapped Types and Overloads
 * Tests if the parser handles complex syntax without breaking.
 */
export interface DataMap {
    [key: string]: string | number | boolean;
}

export type ReadonlyData<T> = {
    readonly [P in keyof T]: T[P];
};

export class OverloadedMethod {
    process(input: string): string;
    process(input: number): number;
    process(input: any): any {
        return input;
    }
}

/**
 * Tough Case 6: Private Fields and Mixed Scopes
 */
export class PrivacyTest {
    #realPrivate = "hidden"; // ES2020 private field
    private tsPrivate = "pseudo"; // TypeScript private

    getPrivate() {
        return this.#realPrivate;
    }
}
