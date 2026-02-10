/**
 * Modules and Namespaces
 * Demonstrates TypeScript's module system, imports/exports, namespaces,
 * ambient declarations, and advanced module patterns
 */

// ========== Basic Exports ==========
export const MODULE_VERSION = "1.0.0";
export const DEFAULT_CONFIG = {
  debug: false,
  timeout: 5000,
  retries: 3
};

// Named export
export function calculateSum(a: number, b: number): number {
  return a + b;
}

// Export with alias
export { calculateSum as add };

// Multiple exports
export const PI = Math.PI;
export const E = Math.E;

// ========== Default Export ==========
class DefaultLogger {
  private prefix: string;
  
  constructor(prefix: string = "LOG") {
    this.prefix = prefix;
  }
  
  log(message: string): void {
    console.log(`[${this.prefix}] ${message}`);
  }
  
  error(message: string): void {
    console.error(`[${this.prefix}] ERROR: ${message}`);
  }
}

export default DefaultLogger;

// ========== Re-exports ==========
// Re-export everything from types-interfaces
export * from './types-interfaces';

// Re-export specific items with aliases
export { 
  Person as BasePerson, 
  Employee as StaffMember 
} from './classes-inheritance';

// Re-export default with a name
export { default as Logger } from './modules-namespaces';

// ========== Namespace Declarations ==========
export namespace MathUtils {
  export interface Point2D {
    x: number;
    y: number;
  }
  
  export interface Point3D extends Point2D {
    z: number;
  }
  
  export class Vector2D implements Point2D {
    constructor(public x: number, public y: number) {}
    
    add(other: Vector2D): Vector2D {
      return new Vector2D(this.x + other.x, this.y + other.y);
    }
    
    magnitude(): number {
      return Math.sqrt(this.x * this.x + this.y * this.y);
    }
  }
  
  export class Vector3D implements Point3D {
    constructor(public x: number, public y: number, public z: number) {}
    
    add(other: Vector3D): Vector3D {
      return new Vector3D(this.x + other.x, this.y + other.y, this.z + other.z);
    }
    
    magnitude(): number {
      return Math.sqrt(this.x * this.x + this.y * this.y + this.z * this.z);
    }
  }
  
  export function distance2D(p1: Point2D, p2: Point2D): number {
    const dx = p1.x - p2.x;
    const dy = p1.y - p2.y;
    return Math.sqrt(dx * dx + dy * dy);
  }
  
  export function distance3D(p1: Point3D, p2: Point3D): number {
    const dx = p1.x - p2.x;
    const dy = p1.y - p2.y;
    const dz = p1.z - p2.z;
    return Math.sqrt(dx * dx + dy * dy + dz * dz);
  }
  
  export namespace Constants {
    export const GOLDEN_RATIO = 1.618033988749895;
    export const EULER_CONSTANT = 0.5772156649015329;
    export const SQRT_2 = Math.sqrt(2);
  }
}

// Nested namespace
export namespace DataStructures {
  export namespace Trees {
    export interface TreeNode<T> {
      value: T;
      left?: TreeNode<T>;
      right?: TreeNode<T>;
    }
    
    export class BinaryTree<T> {
      constructor(public root?: TreeNode<T>) {}
      
      insert(value: T): void {
        this.root = this.insertNode(this.root, value);
      }
      
      private insertNode(node: TreeNode<T> | undefined, value: T): TreeNode<T> {
        if (!node) {
          return { value };
        }
        
        // Simple insertion based on string comparison
        if (String(value) < String(node.value)) {
          node.left = this.insertNode(node.left, value);
        } else {
          node.right = this.insertNode(node.right, value);
        }
        
        return node;
      }
    }
  }
  
  export namespace Graphs {
    export interface Edge<T> {
      from: T;
      to: T;
      weight?: number;
    }
    
    export class Graph<T> {
      private adjacencyList: Map<T, T[]> = new Map();
      
      addVertex(vertex: T): void {
        if (!this.adjacencyList.has(vertex)) {
          this.adjacencyList.set(vertex, []);
        }
      }
      
      addEdge(from: T, to: T): void {
        this.addVertex(from);
        this.addVertex(to);
        this.adjacencyList.get(from)!.push(to);
      }
      
      getNeighbors(vertex: T): T[] {
        return this.adjacencyList.get(vertex) || [];
      }
      
      getVertices(): T[] {
        return Array.from(this.adjacencyList.keys());
      }
    }
  }
}

// ========== Module Augmentation ==========
// Extending existing modules
declare global {
  interface String {
    toTitleCase(): string;
    truncate(length: number): string;
  }
  
  interface Array<T> {
    chunk(size: number): T[][];
    unique(): T[];
  }
}

// Implement the extensions
String.prototype.toTitleCase = function(): string {
  return this.replace(/\w\S*/g, (txt) => 
    txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase()
  );
};

String.prototype.truncate = function(length: number): string {
  return this.length > length ? this.substring(0, length) + '...' : this.toString();
};

Array.prototype.chunk = function<T>(this: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < this.length; i += size) {
    chunks.push(this.slice(i, i + size));
  }
  return chunks;
};

Array.prototype.unique = function<T>(this: T[]): T[] {
  return [...new Set(this)];
};

// ========== Ambient Declarations ==========
// Declare external libraries or global variables
declare global {
  var GLOBAL_CONFIG: {
    apiUrl: string;
    version: string;
    features: string[];
  };
}

// Ambient module declaration
declare module "fictional-library" {
  export interface Config {
    apiKey: string;
    endpoint: string;
  }
  
  export class Client {
    constructor(config: Config);
    request(path: string): Promise<any>;
  }
  
  export function initialize(config: Config): Client;
}

// Declare a module with wildcard
declare module "*.json" {
  const value: any;
  export default value;
}

declare module "*.svg" {
  const content: string;
  export default content;
}

// ========== Conditional Exports ==========
export interface DatabaseConnection {
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  query(sql: string): Promise<any[]>;
}

// Different implementations based on environment
const isDevelopment = process.env.NODE_ENV === 'development';

export const createDatabaseConnection = (): DatabaseConnection => {
  if (isDevelopment) {
    return new MockDatabaseConnection();
  } else {
    return new ProductionDatabaseConnection();
  }
};

class MockDatabaseConnection implements DatabaseConnection {
  async connect(): Promise<void> {
    console.log("Connected to mock database");
  }
  
  async disconnect(): Promise<void> {
    console.log("Disconnected from mock database");
  }
  
  async query(sql: string): Promise<any[]> {
    console.log(`Mock query: ${sql}`);
    return [{ id: 1, name: "Mock Data" }];
  }
}

class ProductionDatabaseConnection implements DatabaseConnection {
  async connect(): Promise<void> {
    console.log("Connected to production database");
  }
  
  async disconnect(): Promise<void> {
    console.log("Disconnected from production database");
  }
  
  async query(sql: string): Promise<any[]> {
    console.log(`Production query: ${sql}`);
    // Would connect to real database
    return [];
  }
}

// ========== Dynamic Imports ==========
export async function loadModule(moduleName: string): Promise<any> {
  try {
    switch (moduleName) {
      case 'math':
        return await import('./functions-generics');
      case 'classes':
        return await import('./classes-inheritance');
      case 'types':
        return await import('./types-interfaces');
      default:
        throw new Error(`Module ${moduleName} not found`);
    }
  } catch (error) {
    console.error(`Failed to load module ${moduleName}:`, error);
    throw error;
  }
}

// Dynamic import with type assertion
export async function loadTypedModule<T>(): Promise<T> {
  const module = await import('./types-interfaces');
  return module as T;
}

// ========== Module Factory Pattern ==========
export interface ModuleConfig {
  name: string;
  version: string;
  dependencies?: string[];
}

export abstract class BaseModule {
  constructor(protected config: ModuleConfig) {}
  
  abstract initialize(): Promise<void>;
  abstract cleanup(): Promise<void>;
  
  getConfig(): ModuleConfig {
    return this.config;
  }
}

export class FeatureModule extends BaseModule {
  private isInitialized = false;
  
  async initialize(): Promise<void> {
    console.log(`Initializing ${this.config.name} v${this.config.version}`);
    
    if (this.config.dependencies) {
      for (const dep of this.config.dependencies) {
        await this.loadDependency(dep);
      }
    }
    
    this.isInitialized = true;
  }
  
  async cleanup(): Promise<void> {
    console.log(`Cleaning up ${this.config.name}`);
    this.isInitialized = false;
  }
  
  private async loadDependency(name: string): Promise<void> {
    console.log(`Loading dependency: ${name}`);
    // Simulate loading dependency
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  
  isReady(): boolean {
    return this.isInitialized;
  }
}

// ========== Barrel Exports ==========
// This file can serve as a barrel export for the entire project
export {
  // Re-export all from other modules to create a single entry point
  createUser,
  greet,
  sum
} from './functions-generics';

export {
  EventEmitter,
  PromisePool,
  AsyncCache
} from './async-promises';

// ========== Triple-Slash Directives ==========
/// <reference types="node" />
/// <reference lib="es2020" />

// ========== Usage Examples ==========
export const moduleExamples = {
  // Math utilities
  vector2D: new MathUtils.Vector2D(3, 4),
  vector3D: new MathUtils.Vector3D(1, 2, 3),
  distance: MathUtils.distance2D({ x: 0, y: 0 }, { x: 3, y: 4 }),
  
  // Data structures
  binaryTree: new DataStructures.Trees.BinaryTree<number>(),
  graph: new DataStructures.Graphs.Graph<string>(),
  
  // String extensions (using global augmentation)
  titleCase: "hello world".toTitleCase(),
  truncated: "This is a very long string".truncate(10),
  
  // Array extensions
  chunked: [1, 2, 3, 4, 5, 6].chunk(2),
  uniqueArray: [1, 2, 2, 3, 3, 3].unique(),
  
  // Module factory
  featureModule: new FeatureModule({
    name: "SampleFeature",
    version: "1.0.0",
    dependencies: ["core", "utils"]
  }),
  
  // Database connection
  dbConnection: createDatabaseConnection()
};

// Initialize examples
moduleExamples.binaryTree.insert(5);
moduleExamples.binaryTree.insert(3);
moduleExamples.binaryTree.insert(7);

moduleExamples.graph.addVertex("A");
moduleExamples.graph.addVertex("B");
moduleExamples.graph.addEdge("A", "B");

// Constants from nested namespace
export const mathConstants = {
  goldenRatio: MathUtils.Constants.GOLDEN_RATIO,
  eulerConstant: MathUtils.Constants.EULER_CONSTANT,
  sqrt2: MathUtils.Constants.SQRT_2
};

// ========== Module Types ==========
export type ModuleLoader = (name: string) => Promise<any>;
export type ModuleRegistry = Map<string, BaseModule>;

export interface ModuleSystem {
  register(name: string, module: BaseModule): void;
  unregister(name: string): void;
  get(name: string): BaseModule | undefined;
  has(name: string): boolean;
  initialize(): Promise<void>;
  shutdown(): Promise<void>;
}