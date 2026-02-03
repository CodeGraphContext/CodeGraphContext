/**
 * Advanced Types
 * Demonstrates TypeScript's advanced type system including mapped types,
 * conditional types, template literal types, type manipulation, and complex patterns
 */

// ========== Mapped Types ==========
export type Optional<T> = {
  [K in keyof T]?: T[K];
};

export type Required<T> = {
  [K in keyof T]-?: T[K];
};

export type Readonly<T> = {
  readonly [K in keyof T]: T[K];
};

export type Mutable<T> = {
  -readonly [K in keyof T]: T[K];
};

// Custom mapped type with transformation
export type Stringify<T> = {
  [K in keyof T]: string;
};

export type Nullify<T> = {
  [K in keyof T]: T[K] | null;
};

// Mapped type with key transformation
export type Getters<T> = {
  [K in keyof T as `get${Capitalize<string & K>}`]: () => T[K];
};

export type Setters<T> = {
  [K in keyof T as `set${Capitalize<string & K>}`]: (value: T[K]) => void;
};

// ========== Conditional Types ==========
export type NonNullable<T> = T extends null | undefined ? never : T;

export type IsArray<T> = T extends any[] ? true : false;

export type ArrayElementType<T> = T extends (infer U)[] ? U : never;

export type ReturnTypeOf<T> = T extends (...args: any[]) => infer R ? R : never;

export type ParametersOf<T> = T extends (...args: infer P) => any ? P : never;

// Complex conditional type
export type DeepReadonly<T> = T extends (infer U)[]
  ? DeepReadonlyArray<U>
  : T extends object
  ? DeepReadonlyObject<T>
  : T;

interface DeepReadonlyArray<T> extends ReadonlyArray<DeepReadonly<T>> {}

type DeepReadonlyObject<T> = {
  readonly [K in keyof T]: DeepReadonly<T[K]>;
};

// Conditional type with multiple conditions
export type TypeName<T> = T extends string
  ? "string"
  : T extends number
  ? "number"
  : T extends boolean
  ? "boolean"
  : T extends undefined
  ? "undefined"
  : T extends Function
  ? "function"
  : "object";

// ========== Template Literal Types ==========
export type EventNames<T extends string> = `${T}Changed` | `${T}Updated` | `before${Capitalize<T>}`;

export type HttpMethod = "GET" | "POST" | "PUT" | "DELETE";
export type ApiEndpoint<T extends string> = `api/${T}`;
export type ApiUrl<T extends string, M extends HttpMethod> = `${M} /${ApiEndpoint<T>}`;

// CSS-in-JS style types
export type CSSProperty = `--${string}` | keyof CSSStyleDeclaration;
export type PixelValue<T extends number> = `${T}px`;
export type PercentValue<T extends number> = `${T}%`;

// Path-like template literals
export type Join<K, P> = K extends string | number
  ? P extends string | number
    ? `${K}${"" extends P ? "" : "."}${P}`
    : never
  : never;

export type Paths<T, D extends number = 10> = [D] extends [never]
  ? never
  : T extends object
  ? {
      [K in keyof T]-?: K extends string | number
        ? `${K}` | Join<K, Paths<T[K], Prev[D]>>
        : never;
    }[keyof T]
  : "";

type Prev = [never, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, ...0[]];

// ========== Utility Types and Type Manipulation ==========
export type PickByType<T, U> = Pick<T, { [K in keyof T]: T[K] extends U ? K : never }[keyof T]>;

export type OmitByType<T, U> = Omit<T, { [K in keyof T]: T[K] extends U ? K : never }[keyof T]>;

export type ExcludeKeys<T, K extends keyof T> = Pick<T, Exclude<keyof T, K>>;

export type KeysOfType<T, U> = { [K in keyof T]: T[K] extends U ? K : never }[keyof T];

// Deep pick utility
export type DeepPick<T, K extends Paths<T>> = K extends `${infer Key}.${infer Rest}`
  ? Key extends keyof T
    ? { [P in Key]: DeepPick<T[P], Rest> }
    : never
  : K extends keyof T
  ? { [P in K]: T[P] }
  : never;

// Function type utilities
export type Promisify<T> = T extends (...args: infer A) => infer R
  ? (...args: A) => Promise<R>
  : never;

export type Curry<T> = T extends (...args: infer A) => infer R
  ? A extends [infer First, ...infer Rest]
    ? (arg: First) => Rest extends []
      ? R
      : Curry<(...args: Rest) => R>
    : () => R
  : never;

// ========== Recursive Types ==========
export type DeepPartial<T> = T extends object
  ? {
      [P in keyof T]?: DeepPartial<T[P]>;
    }
  : T;

export type DeepRequired<T> = T extends object
  ? {
      [P in keyof T]-?: DeepRequired<T[P]>;
    }
  : T;

// JSON type
export type JSONValue = string | number | boolean | null | JSONObject | JSONArray;
interface JSONObject {
  [key: string]: JSONValue;
}
interface JSONArray extends Array<JSONValue> {}

// ========== Branded Types ==========
declare const __brand: unique symbol;
type Brand<T, TBrand extends string> = T & { [__brand]: TBrand };

export type UserId = Brand<number, "UserId">;
export type Email = Brand<string, "Email">;
export type Timestamp = Brand<number, "Timestamp">;

// Brand creation utilities
export const createUserId = (id: number): UserId => id as UserId;
export const createEmail = (email: string): Email => {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw new Error("Invalid email format");
  }
  return email as Email;
};

// ========== Tuple Utilities ==========
export type Head<T extends readonly any[]> = T extends readonly [infer H, ...any[]] ? H : never;
export type Tail<T extends readonly any[]> = T extends readonly [any, ...infer Rest] ? Rest : [];
export type Last<T extends readonly any[]> = T extends readonly [...any[], infer L] ? L : never;
export type Length<T extends readonly any[]> = T["length"];

export type Reverse<T extends any[]> = T extends [...infer Rest, infer Last]
  ? [Last, ...Reverse<Rest>]
  : [];

// ========== String Manipulation Types ==========
export type Uppercase<S extends string> = intrinsic;
export type Lowercase<S extends string> = intrinsic;
export type Capitalize<S extends string> = intrinsic;
export type Uncapitalize<S extends string> = intrinsic;

export type Split<S extends string, D extends string> = string extends S
  ? string[]
  : S extends ""
  ? []
  : S extends `${infer T}${D}${infer U}`
  ? [T, ...Split<U, D>]
  : [S];

export type Join<T extends string[], D extends string> = T extends [
  infer First,
  ...infer Rest
]
  ? First extends string
    ? Rest extends string[]
      ? Rest["length"] extends 0
        ? First
        : `${First}${D}${Join<Rest, D>}`
      : never
    : never
  : "";

// ========== Advanced Pattern Matching ==========
export type ExtractRouteParams<T extends string> = T extends `${string}:${infer Param}/${infer Rest}`
  ? { [K in Param]: string } & ExtractRouteParams<Rest>
  : T extends `${string}:${infer Param}`
  ? { [K in Param]: string }
  : {};

export type ParseQueryString<T extends string> = T extends `${infer Key}=${infer Value}&${infer Rest}`
  ? { [K in Key]: Value } & ParseQueryString<Rest>
  : T extends `${infer Key}=${infer Value}`
  ? { [K in Key]: Value }
  : {};

// ========== Type Predicates and Guards ==========
export type IsUnion<T, U = T> = T extends U ? ([U] extends [T] ? false : true) : false;
export type IsNever<T> = [T] extends [never] ? true : false;
export type IsAny<T> = 0 extends 1 & T ? true : false;
export type IsUnknown<T> = IsAny<T> extends true ? false : unknown extends T ? true : false;

// ========== Higher-Kinded Types Simulation ==========
export interface Functor<F> {
  map<A, B>(fn: (a: A) => B): <T extends F>(fa: T) => T extends HKT<F, A> ? HKT<F, B> : never;
}

export interface HKT<F, A> {
  _F: F;
  _A: A;
}

// Array functor instance
export type ArrayHKT = "Array";
export interface ArrayF<A> extends HKT<ArrayHKT, A> {
  _tag: A[];
}

// ========== Example Usage Types ==========
interface User {
  id: number;
  name: string;
  email: string;
  age: number;
  address: {
    street: string;
    city: string;
    country: string;
  };
  preferences: {
    theme: "light" | "dark";
    notifications: boolean;
  };
}

// Applied utility types
export type Examples = {
  // Mapped types
  optionalUser: Optional<User>;
  readonlyUser: Readonly<User>;
  stringifiedUser: Stringify<User>;
  
  // Conditional types
  userIsArray: IsArray<User>;
  userArrayElement: ArrayElementType<User[]>;
  nonNullableString: NonNullable<string | null>;
  
  // Template literals
  userEventNames: EventNames<"user">;
  apiEndpoints: ApiUrl<"users", "GET"> | ApiUrl<"posts", "POST">;
  
  // Utility combinations
  userOnlyStrings: PickByType<User, string>;
  userWithoutStrings: OmitByType<User, string>;
  userPaths: Paths<User>;
  
  // Branded types
  userId: UserId;
  userEmail: Email;
  
  // Advanced patterns
  routeParams: ExtractRouteParams<"/users/:id/posts/:postId">;
  queryParams: ParseQueryString<"search=typescript&sort=date&limit=10">;
};

// ========== Complex Type Challenges ==========
// Function composition types
export type Compose<F extends any[], T = any> = F extends [
  (...args: any[]) => infer R
]
  ? (arg: T) => R
  : F extends [(...args: any[]) => infer R, ...infer Rest]
  ? (arg: T) => Compose<Rest, R>
  : never;

// Object path access
export type Get<T, K> = K extends `${infer Key}.${infer Rest}`
  ? Key extends keyof T
    ? Get<T[Key], Rest>
    : never
  : K extends keyof T
  ? T[K]
  : never;

// Type-safe SQL-like operations
export type Select<T, K extends keyof T> = Pick<T, K>;
export type Where<T, K extends keyof T, V> = T[K] extends V ? T : never;
export type OrderBy<T, K extends keyof T> = T; // Simplified for demo

// State machine types
export type StateMachine<States extends string, Events extends string> = {
  [S in States]: {
    [E in Events]?: States;
  };
};

export type UserStateMachine = StateMachine<
  "idle" | "loading" | "success" | "error",
  "fetch" | "success" | "error" | "reset"
>;

// ========== Type-Level Arithmetic (Basic) ==========
export type Add<A extends number, B extends number> = [...Tuple<A>, ...Tuple<B>]["length"];
export type Tuple<T extends number> = T extends T ? (T extends 0 ? [] : [...Tuple<Subtract<T, 1>>, any]) : never;
export type Subtract<A extends number, B extends number> = Tuple<A> extends [...infer U, ...Tuple<B>] ? U["length"] : never;

// ========== Usage Examples ==========
export const advancedTypesExamples = {
  // Branded types usage
  userId: createUserId(123),
  userEmail: createEmail("user@example.com"),
  
  // Template literal types
  apiUrl: "GET /api/users" as ApiUrl<"users", "GET">,
  
  // Complex type transformations
  userPaths: ["id", "name", "email", "address.street", "preferences.theme"] as Paths<User>[],
  
  // Type predicates
  isUnion: false as IsUnion<string | number>,
  isNever: false as IsNever<never>,
  isAny: false as IsAny<any>,
};

// Example of using advanced types in practice
export function createTypeSafeGetter<T>() {
  return function get<K extends Paths<T>>(obj: T, path: K): Get<T, K> {
    const keys = path.split('.') as string[];
    let result: any = obj;
    
    for (const key of keys) {
      result = result?.[key];
    }
    
    return result as Get<T, K>;
  };
}

// Usage of the type-safe getter
const userGetter = createTypeSafeGetter<User>();
export const getExample = {
  userName: userGetter({} as User, "name"), // Type is string
  userCity: userGetter({} as User, "address.city"), // Type is string
  userTheme: userGetter({} as User, "preferences.theme"), // Type is "light" | "dark"
};