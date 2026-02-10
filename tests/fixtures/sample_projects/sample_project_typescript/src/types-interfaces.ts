/**
 * Basic Types and Interfaces
 * Demonstrates TypeScript's core type system including primitives,
 * interfaces, type aliases, unions, intersections, and advanced type patterns
 */

// ========== Primitive Types ==========
export const stringValue: string = "Hello TypeScript";
export const numberValue: number = 42;
export const booleanValue: boolean = true;
export const nullValue: null = null;
export const undefinedValue: undefined = undefined;
export const symbolValue: symbol = Symbol("unique");
export const bigintValue: bigint = 100n;

// ========== Array and Tuple Types ==========
export const numberArray: number[] = [1, 2, 3, 4];
export const stringArray: Array<string> = ["a", "b", "c"];
export const mixedTuple: [string, number, boolean] = ["hello", 42, true];
export const namedTuple: [name: string, age: number] = ["Alice", 30];

// ========== Object Types ==========
export const basicObject: { name: string; age: number } = {
  name: "John",
  age: 25
};

// ========== Interface Definitions ==========
export interface User {
  readonly id: number;
  name: string;
  email?: string; // Optional property
  readonly createdAt: Date;
  preferences: UserPreferences;
}

export interface UserPreferences {
  theme: "light" | "dark";
  notifications: boolean;
  language: string;
}

// Interface inheritance
export interface AdminUser extends User {
  permissions: string[];
  lastLogin?: Date;
}

// Interface with index signature
export interface Dictionary<T = any> {
  [key: string]: T;
}

// Interface with call signature
export interface StringProcessor {
  (input: string): string;
  description: string;
}

// Interface with construct signature
export interface Constructable {
  new (name: string): { name: string };
}

// ========== Type Aliases ==========
export type Status = "pending" | "approved" | "rejected";
export type ID = string | number;
export type EventHandler<T> = (event: T) => void;

// Generic type alias
export type Response<T> = {
  data: T;
  error: string | null;
  timestamp: Date;
};

// Mapped type alias
export type Optional<T> = {
  [K in keyof T]?: T[K];
};

// ========== Union Types ==========
export type StringOrNumber = string | number;
export type Theme = "light" | "dark" | "auto";

export function formatValue(value: StringOrNumber): string {
  if (typeof value === "string") {
    return value.toUpperCase();
  }
  return value.toString();
}

// Discriminated union
export type Shape = 
  | { kind: "circle"; radius: number }
  | { kind: "rectangle"; width: number; height: number }
  | { kind: "triangle"; base: number; height: number };

export function calculateArea(shape: Shape): number {
  switch (shape.kind) {
    case "circle":
      return Math.PI * shape.radius ** 2;
    case "rectangle":
      return shape.width * shape.height;
    case "triangle":
      return (shape.base * shape.height) / 2;
    default:
      const _exhaustive: never = shape;
      throw new Error(`Unhandled shape: ${_exhaustive}`);
  }
}

// ========== Intersection Types ==========
export type PersonalInfo = {
  name: string;
  age: number;
};

export type ContactInfo = {
  email: string;
  phone: string;
};

export type Employee = PersonalInfo & ContactInfo & {
  employeeId: string;
  department: string;
};

// ========== Conditional Types ==========
export type NonNullable<T> = T extends null | undefined ? never : T;
export type ArrayElement<T> = T extends (infer U)[] ? U : never;

// ========== Template Literal Types ==========
export type EventName<T extends string> = `on${Capitalize<T>}`;
export type CSSProperty = `--${string}`;

// ========== Utility Types Usage ==========
export type PartialUser = Partial<User>;
export type RequiredUser = Required<User>;
export type UserEmail = Pick<User, "email">;
export type UserWithoutId = Omit<User, "id">;
export type UserKeys = keyof User;
export type UserValues = User[keyof User];

// ========== Complex Type Examples ==========
export interface GenericRepository<T, K extends keyof T> {
  findById(id: T[K]): Promise<T | null>;
  findAll(): Promise<T[]>;
  create(entity: Omit<T, K>): Promise<T>;
  update(id: T[K], updates: Partial<T>): Promise<T>;
  delete(id: T[K]): Promise<void>;
}

// Recursive type
export interface TreeNode<T> {
  value: T;
  children: TreeNode<T>[];
  parent?: TreeNode<T>;
}

// Function type with overloads
export interface Logger {
  (message: string): void;
  (level: "info" | "warn" | "error", message: string): void;
  (level: "info" | "warn" | "error", message: string, data: any): void;
}

// ========== Implementation Examples ==========
const user: User = {
  id: 1,
  name: "Alice Johnson",
  email: "alice@example.com",
  createdAt: new Date(),
  preferences: {
    theme: "dark",
    notifications: true,
    language: "en"
  }
};

const adminUser: AdminUser = {
  ...user,
  permissions: ["read", "write", "delete"],
  lastLogin: new Date()
};

const shapes: Shape[] = [
  { kind: "circle", radius: 5 },
  { kind: "rectangle", width: 10, height: 6 },
  { kind: "triangle", base: 8, height: 4 }
];

export const typeExamples = {
  user,
  adminUser,
  shapes,
  areas: shapes.map(calculateArea)
};