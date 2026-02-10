/**
 * Functions and Generics
 * Demonstrates TypeScript's function types, overloads, generics, constraints,
 * higher-order functions, and advanced function patterns
 */

// ========== Basic Function Types ==========
export function simpleFunction(x: number, y: number): number {
  return x + y;
}

// Optional parameters
export function greet(name: string, greeting?: string): string {
  return `${greeting || "Hello"}, ${name}!`;
}

// Default parameters
export function createUser(name: string, active: boolean = true): { name: string; active: boolean } {
  return { name, active };
}

// Rest parameters
export function sum(...numbers: number[]): number {
  return numbers.reduce((total, num) => total + num, 0);
}

// ========== Function Overloads ==========
export function parseValue(value: string): number;
export function parseValue(value: number): string;
export function parseValue(value: boolean): string;
export function parseValue(value: string | number | boolean): string | number {
  if (typeof value === "string") {
    return parseInt(value, 10);
  } else if (typeof value === "number") {
    return value.toString();
  } else {
    return value.toString();
  }
}

// Complex overloads
export function processData(data: string[]): string[];
export function processData(data: number[]): number[];
export function processData<T>(data: T[], processor: (item: T) => T): T[];
export function processData<T>(
  data: T[],
  processor?: (item: T) => T
): T[] {
  if (processor) {
    return data.map(processor);
  }
  return [...data];
}

// ========== Arrow Functions ==========
export const multiply = (x: number, y: number): number => x * y;

export const isEven = (n: number): boolean => n % 2 === 0;

// Higher-order arrow function
export const createMultiplier = (factor: number) => (value: number) => value * factor;

// ========== Generic Functions ==========
export function identity<T>(arg: T): T {
  return arg;
}

export function getFirstElement<T>(array: T[]): T | undefined {
  return array[0];
}

// Generic with multiple type parameters
export function merge<T, U>(obj1: T, obj2: U): T & U {
  return { ...obj1, ...obj2 };
}

// Generic with default type parameter
export function createArray<T = string>(length: number, defaultValue: T): T[] {
  return Array(length).fill(defaultValue);
}

// ========== Generic Constraints ==========
// Constraint using extends
export function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key];
}

// Constraint with interface
interface Lengthwise {
  length: number;
}

export function logLength<T extends Lengthwise>(arg: T): T {
  console.log(arg.length);
  return arg;
}

// Constraint with conditional types
export function processItem<T extends string | number>(
  item: T
): T extends string ? string : number {
  if (typeof item === "string") {
    return item.toUpperCase() as T extends string ? string : number;
  }
  return (item * 2) as T extends string ? string : number;
}

// ========== Advanced Generic Patterns ==========
// Generic factory function
export interface Constructable<T = {}> {
  new (...args: any[]): T;
}

export function createInstance<T>(constructor: Constructable<T>, ...args: any[]): T {
  return new constructor(...args);
}

// Generic with constraint and default
export function sortBy<T, K extends keyof T = keyof T>(
  array: T[],
  key: K,
  ascending: boolean = true
): T[] {
  return array.sort((a, b) => {
    const valueA = a[key];
    const valueB = b[key];
    
    if (valueA < valueB) return ascending ? -1 : 1;
    if (valueA > valueB) return ascending ? 1 : -1;
    return 0;
  });
}

// ========== Function Types ==========
export type UnaryFunction<T, R> = (arg: T) => R;
export type BinaryFunction<T, U, R> = (arg1: T, arg2: U) => R;
export type Predicate<T> = (arg: T) => boolean;
export type Mapper<T, R> = (item: T, index: number, array: T[]) => R;

// Function that accepts function types
export function pipe<T, R1, R2>(
  input: T,
  fn1: UnaryFunction<T, R1>,
  fn2: UnaryFunction<R1, R2>
): R2 {
  return fn2(fn1(input));
}

// ========== Higher-Order Functions ==========
export function memoize<T extends (...args: any[]) => any>(fn: T): T {
  const cache = new Map();
  
  return ((...args: any[]) => {
    const key = JSON.stringify(args);
    if (cache.has(key)) {
      return cache.get(key);
    }
    const result = fn(...args);
    cache.set(key, result);
    return result;
  }) as T;
}

export function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delay: number
): T {
  let timeoutId: NodeJS.Timeout;
  
  return ((...args: any[]) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delay);
  }) as T;
}

export function throttle<T extends (...args: any[]) => any>(
  fn: T,
  limit: number
): T {
  let inThrottle: boolean;
  
  return ((...args: any[]) => {
    if (!inThrottle) {
      fn(...args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  }) as T;
}

// ========== Generic Data Structures ==========
export class Stack<T> {
  private items: T[] = [];

  push(item: T): void {
    this.items.push(item);
  }

  pop(): T | undefined {
    return this.items.pop();
  }

  peek(): T | undefined {
    return this.items[this.items.length - 1];
  }

  isEmpty(): boolean {
    return this.items.length === 0;
  }

  size(): number {
    return this.items.length;
  }
}

export class Queue<T> {
  private items: T[] = [];

  enqueue(item: T): void {
    this.items.push(item);
  }

  dequeue(): T | undefined {
    return this.items.shift();
  }

  front(): T | undefined {
    return this.items[0];
  }

  isEmpty(): boolean {
    return this.items.length === 0;
  }

  size(): number {
    return this.items.length;
  }
}

// Generic with multiple constraints
export interface Comparable<T> {
  compareTo(other: T): number;
}

export class PriorityQueue<T extends Comparable<T>> {
  private items: T[] = [];

  enqueue(item: T): void {
    this.items.push(item);
    this.items.sort((a, b) => a.compareTo(b));
  }

  dequeue(): T | undefined {
    return this.items.shift();
  }

  peek(): T | undefined {
    return this.items[0];
  }

  isEmpty(): boolean {
    return this.items.length === 0;
  }
}

// ========== Utility Functions with Generics ==========
export function arrayChunk<T>(array: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < array.length; i += size) {
    chunks.push(array.slice(i, i + size));
  }
  return chunks;
}

export function arrayUnique<T>(array: T[]): T[] {
  return [...new Set(array)];
}

export function arrayGroupBy<T, K extends string | number | symbol>(
  array: T[],
  keyFn: (item: T) => K
): Record<K, T[]> {
  return array.reduce((groups, item) => {
    const key = keyFn(item);
    groups[key] = groups[key] || [];
    groups[key]!.push(item);
    return groups;
  }, {} as Record<K, T[]>);
}

// Curried functions
export const curriedAdd = (x: number) => (y: number) => x + y;
export const curriedFilter = <T>(predicate: Predicate<T>) => (array: T[]) => 
  array.filter(predicate);

// ========== Generic Utility Types Functions ==========
export function pick<T, K extends keyof T>(obj: T, ...keys: K[]): Pick<T, K> {
  const result = {} as Pick<T, K>;
  keys.forEach(key => {
    result[key] = obj[key];
  });
  return result;
}

export function omit<T, K extends keyof T>(obj: T, ...keys: K[]): Omit<T, K> {
  const result = { ...obj };
  keys.forEach(key => {
    delete result[key];
  });
  return result as Omit<T, K>;
}

export function deepClone<T>(obj: T): T {
  if (obj === null || typeof obj !== "object") {
    return obj;
  }
  
  if (obj instanceof Date) {
    return new Date(obj.getTime()) as T;
  }
  
  if (obj instanceof Array) {
    return obj.map(item => deepClone(item)) as T;
  }
  
  if (typeof obj === "object") {
    const copy = {} as T;
    Object.keys(obj).forEach(key => {
      (copy as any)[key] = deepClone((obj as any)[key]);
    });
    return copy;
  }
  
  return obj;
}

// ========== Function Composition ==========
export function compose<T, R1, R2>(
  fn1: (arg: T) => R1,
  fn2: (arg: R1) => R2
): (arg: T) => R2;
export function compose<T, R1, R2, R3>(
  fn1: (arg: T) => R1,
  fn2: (arg: R1) => R2,
  fn3: (arg: R2) => R3
): (arg: T) => R3;
export function compose(...fns: Function[]) {
  return (arg: any) => fns.reduce((result, fn) => fn(result), arg);
}

// ========== Usage Examples ==========
export const functionExamples = {
  // Basic functions
  basicSum: sum(1, 2, 3, 4, 5),
  parsedString: parseValue("123"),
  parsedNumber: parseValue(456),
  
  // Generics
  identityString: identity("hello"),
  identityNumber: identity(42),
  mergedObject: merge({ name: "John" }, { age: 30 }),
  
  // Data structures
  numberStack: new Stack<number>(),
  stringQueue: new Queue<string>(),
  
  // Higher-order functions
  double: createMultiplier(2),
  memoizedFib: memoize((n: number): number => {
    if (n <= 1) return n;
    return functionExamples.memoizedFib(n - 1) + functionExamples.memoizedFib(n - 2);
  }),
  
  // Array utilities
  chunkedArray: arrayChunk([1, 2, 3, 4, 5, 6, 7], 3),
  uniqueArray: arrayUnique([1, 2, 2, 3, 3, 3, 4]),
  groupedItems: arrayGroupBy(
    [{ type: "fruit", name: "apple" }, { type: "fruit", name: "banana" }, { type: "vegetable", name: "carrot" }],
    item => item.type
  )
};

// Initialize some examples
functionExamples.numberStack.push(1);
functionExamples.numberStack.push(2);
functionExamples.numberStack.push(3);

functionExamples.stringQueue.enqueue("first");
functionExamples.stringQueue.enqueue("second");
functionExamples.stringQueue.enqueue("third");