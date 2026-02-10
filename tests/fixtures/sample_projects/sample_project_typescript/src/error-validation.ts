/**
 * Error Handling and Validation
 * Demonstrates TypeScript's error handling patterns, custom error types,
 * type guards, assertion functions, and validation patterns
 */

// ========== Custom Error Classes ==========
export class ApplicationError extends Error {
  public readonly code: string;
  public readonly timestamp: Date;
  public readonly context?: Record<string, any>;

  constructor(message: string, code: string, context?: Record<string, any>) {
    super(message);
    this.name = "ApplicationError";
    this.code = code;
    this.timestamp = new Date();
    this.context = context;
    
    // Maintains proper stack trace for where our error was thrown (only available on V8)
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, ApplicationError);
    }
  }
}

export class ValidationError extends ApplicationError {
  public readonly field?: string;
  public readonly value?: any;

  constructor(message: string, field?: string, value?: any, context?: Record<string, any>) {
    super(message, "VALIDATION_ERROR", context);
    this.name = "ValidationError";
    this.field = field;
    this.value = value;
  }
}

export class NotFoundError extends ApplicationError {
  public readonly resource: string;
  public readonly identifier: any;

  constructor(resource: string, identifier: any, context?: Record<string, any>) {
    super(`${resource} with identifier "${identifier}" not found`, "NOT_FOUND", context);
    this.name = "NotFoundError";
    this.resource = resource;
    this.identifier = identifier;
  }
}

export class UnauthorizedError extends ApplicationError {
  constructor(message: string = "Access denied", context?: Record<string, any>) {
    super(message, "UNAUTHORIZED", context);
    this.name = "UnauthorizedError";
  }
}

export class NetworkError extends ApplicationError {
  public readonly statusCode?: number;
  public readonly url?: string;

  constructor(message: string, statusCode?: number, url?: string, context?: Record<string, any>) {
    super(message, "NETWORK_ERROR", context);
    this.name = "NetworkError";
    this.statusCode = statusCode;
    this.url = url;
  }
}

// ========== Result Pattern ==========
export type Result<T, E = Error> = 
  | { success: true; data: T; error?: never }
  | { success: false; data?: never; error: E };

export const Ok = <T>(data: T): Result<T, never> => ({ success: true, data });
export const Err = <E>(error: E): Result<never, E> => ({ success: false, error });

export function isOk<T, E>(result: Result<T, E>): result is { success: true; data: T } {
  return result.success;
}

export function isErr<T, E>(result: Result<T, E>): result is { success: false; error: E } {
  return !result.success;
}

// Result utility functions
export function map<T, U, E>(
  result: Result<T, E>,
  fn: (data: T) => U
): Result<U, E> {
  return isOk(result) ? Ok(fn(result.data)) : result;
}

export function flatMap<T, U, E>(
  result: Result<T, E>,
  fn: (data: T) => Result<U, E>
): Result<U, E> {
  return isOk(result) ? fn(result.data) : result;
}

export function mapError<T, E, F>(
  result: Result<T, E>,
  fn: (error: E) => F
): Result<T, F> {
  return isErr(result) ? Err(fn(result.error)) : result;
}

// ========== Type Guards ==========
export function isString(value: unknown): value is string {
  return typeof value === "string";
}

export function isNumber(value: unknown): value is number {
  return typeof value === "number" && !isNaN(value);
}

export function isObject(value: unknown): value is object {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isArray<T>(value: unknown, elementGuard: (item: unknown) => item is T): value is T[] {
  return Array.isArray(value) && value.every(elementGuard);
}

export function hasProperty<K extends string>(
  obj: unknown,
  prop: K
): obj is Record<K, unknown> {
  return isObject(obj) && prop in obj;
}

export function hasProperties<K extends string>(
  obj: unknown,
  ...props: K[]
): obj is Record<K, unknown> {
  return isObject(obj) && props.every(prop => prop in obj);
}

// Advanced type guards
export function isInstanceOf<T extends new (...args: any[]) => any>(
  constructor: T,
  value: unknown
): value is InstanceType<T> {
  return value instanceof constructor;
}

export function isOneOf<T extends readonly unknown[]>(
  values: T,
  value: unknown
): value is T[number] {
  return values.includes(value);
}

// ========== Assertion Functions ==========
export function assert(condition: any, message?: string): asserts condition {
  if (!condition) {
    throw new Error(message || "Assertion failed");
  }
}

export function assertIsString(value: unknown): asserts value is string {
  if (!isString(value)) {
    throw new ValidationError("Expected string", "value", value);
  }
}

export function assertIsNumber(value: unknown): asserts value is number {
  if (!isNumber(value)) {
    throw new ValidationError("Expected number", "value", value);
  }
}

export function assertIsObject(value: unknown): asserts value is object {
  if (!isObject(value)) {
    throw new ValidationError("Expected object", "value", value);
  }
}

export function assertHasProperty<K extends string>(
  obj: unknown,
  prop: K
): asserts obj is Record<K, unknown> {
  if (!hasProperty(obj, prop)) {
    throw new ValidationError(`Expected property "${prop}"`, prop, obj);
  }
}

export function assertNever(value: never): never {
  throw new Error(`Unexpected value: ${JSON.stringify(value)}`);
}

// ========== Validation Schemas ==========
export interface ValidationRule<T> {
  validate: (value: T) => boolean;
  message: string;
}

export interface Schema<T> {
  rules: ValidationRule<T>[];
  optional?: boolean;
  transform?: (value: any) => T;
}

export class SchemaValidator {
  static validate<T>(value: unknown, schema: Schema<T>): Result<T, ValidationError> {
    // Handle optional values
    if (value === undefined || value === null) {
      if (schema.optional) {
        return Ok(value as T);
      } else {
        return Err(new ValidationError("Value is required"));
      }
    }

    // Transform value if transformer is provided
    let processedValue: T;
    if (schema.transform) {
      try {
        processedValue = schema.transform(value);
      } catch (error) {
        return Err(new ValidationError(`Transformation failed: ${error}`));
      }
    } else {
      processedValue = value as T;
    }

    // Run validation rules
    for (const rule of schema.rules) {
      if (!rule.validate(processedValue)) {
        return Err(new ValidationError(rule.message, "value", value));
      }
    }

    return Ok(processedValue);
  }

  static validateObject<T extends Record<string, any>>(
    value: unknown,
    schemas: { [K in keyof T]: Schema<T[K]> }
  ): Result<T, ValidationError[]> {
    if (!isObject(value)) {
      return Err([new ValidationError("Expected object", "root", value)]);
    }

    const result = {} as T;
    const errors: ValidationError[] = [];

    for (const [key, schema] of Object.entries(schemas)) {
      const fieldValue = (value as any)[key];
      const fieldResult = SchemaValidator.validate(fieldValue, schema);

      if (isOk(fieldResult)) {
        (result as any)[key] = fieldResult.data;
      } else {
        const error = fieldResult.error;
        error.field = key;
        errors.push(error);
      }
    }

    return errors.length === 0 ? Ok(result) : Err(errors);
  }
}

// ========== Common Validation Rules ==========
export const ValidationRules = {
  required: <T>(): ValidationRule<T> => ({
    validate: (value) => value !== undefined && value !== null && value !== "",
    message: "Value is required"
  }),

  minLength: (min: number): ValidationRule<string> => ({
    validate: (value) => value.length >= min,
    message: `Minimum length is ${min}`
  }),

  maxLength: (max: number): ValidationRule<string> => ({
    validate: (value) => value.length <= max,
    message: `Maximum length is ${max}`
  }),

  email: (): ValidationRule<string> => ({
    validate: (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
    message: "Invalid email format"
  }),

  min: (min: number): ValidationRule<number> => ({
    validate: (value) => value >= min,
    message: `Value must be at least ${min}`
  }),

  max: (max: number): ValidationRule<number> => ({
    validate: (value) => value <= max,
    message: `Value must be at most ${max}`
  }),

  regex: (pattern: RegExp, message?: string): ValidationRule<string> => ({
    validate: (value) => pattern.test(value),
    message: message || `Value does not match pattern ${pattern}`
  }),

  oneOf: <T>(values: T[]): ValidationRule<T> => ({
    validate: (value) => values.includes(value),
    message: `Value must be one of: ${values.join(", ")}`
  }),

  custom: <T>(fn: (value: T) => boolean, message: string): ValidationRule<T> => ({
    validate: fn,
    message
  })
};

// ========== Safe Parsing Functions ==========
export function safeParseInt(value: string): Result<number, ValidationError> {
  const parsed = parseInt(value, 10);
  if (isNaN(parsed)) {
    return Err(new ValidationError("Invalid integer", "value", value));
  }
  return Ok(parsed);
}

export function safeParseFloat(value: string): Result<number, ValidationError> {
  const parsed = parseFloat(value);
  if (isNaN(parsed)) {
    return Err(new ValidationError("Invalid float", "value", value));
  }
  return Ok(parsed);
}

export function safeParse<T>(
  value: string,
  parser: (str: string) => T
): Result<T, ValidationError> {
  try {
    return Ok(parser(value));
  } catch (error) {
    return Err(new ValidationError(
      `Parse error: ${error instanceof Error ? error.message : error}`,
      "value",
      value
    ));
  }
}

export function safeJsonParse<T = any>(json: string): Result<T, ValidationError> {
  return safeParse(json, JSON.parse);
}

// ========== Error Boundary Pattern ==========
export class ErrorBoundary {
  private errorHandlers = new Map<string, (error: Error) => void>();
  private globalHandler?: (error: Error) => void;

  onError(type: string, handler: (error: Error) => void): void {
    this.errorHandlers.set(type, handler);
  }

  onGlobalError(handler: (error: Error) => void): void {
    this.globalHandler = handler;
  }

  handle(error: Error): void {
    const handler = this.errorHandlers.get(error.name);
    
    if (handler) {
      handler(error);
    } else if (this.globalHandler) {
      this.globalHandler(error);
    } else {
      console.error("Unhandled error:", error);
    }
  }

  wrap<T extends (...args: any[]) => any>(fn: T): T {
    return ((...args: any[]) => {
      try {
        const result = fn(...args);
        
        // Handle async functions
        if (result instanceof Promise) {
          return result.catch((error) => {
            this.handle(error);
            throw error;
          });
        }
        
        return result;
      } catch (error) {
        if (error instanceof Error) {
          this.handle(error);
        }
        throw error;
      }
    }) as T;
  }
}

// ========== Try-Catch Utilities ==========
export function tryCatch<T>(fn: () => T): Result<T, Error> {
  try {
    return Ok(fn());
  } catch (error) {
    return Err(error instanceof Error ? error : new Error(String(error)));
  }
}

export async function tryCatchAsync<T>(fn: () => Promise<T>): Promise<Result<T, Error>> {
  try {
    const result = await fn();
    return Ok(result);
  } catch (error) {
    return Err(error instanceof Error ? error : new Error(String(error)));
  }
}

// ========== Usage Examples ==========
// Define user schema
const userSchema = {
  id: {
    rules: [ValidationRules.required()],
    transform: (value: any) => parseInt(value, 10)
  } as Schema<number>,
  
  name: {
    rules: [
      ValidationRules.required(),
      ValidationRules.minLength(2),
      ValidationRules.maxLength(100)
    ]
  } as Schema<string>,
  
  email: {
    rules: [
      ValidationRules.required(),
      ValidationRules.email()
    ]
  } as Schema<string>,
  
  age: {
    rules: [
      ValidationRules.min(0),
      ValidationRules.max(120)
    ],
    optional: true,
    transform: (value: any) => parseInt(value, 10)
  } as Schema<number>
};

// Example functions that use error handling
export function validateUser(userData: unknown): Result<{
  id: number;
  name: string;
  email: string;
  age?: number;
}, ValidationError[]> {
  return SchemaValidator.validateObject(userData, userSchema);
}

export async function fetchUser(id: number): Promise<Result<any, ApplicationError>> {
  if (id <= 0) {
    return Err(new ValidationError("Invalid user ID", "id", id));
  }

  // Simulate API call that might fail
  const shouldFail = Math.random() > 0.7;
  
  if (shouldFail) {
    return Err(new NetworkError("Failed to fetch user", 500, `/api/users/${id}`));
  }

  // Simulate user not found
  if (id === 404) {
    return Err(new NotFoundError("User", id));
  }

  return Ok({
    id,
    name: `User ${id}`,
    email: `user${id}@example.com`,
    age: 25
  });
}

// Error boundary usage
export const errorBoundary = new ErrorBoundary();

errorBoundary.onError("ValidationError", (error) => {
  console.error("Validation failed:", error.message);
});

errorBoundary.onError("NetworkError", (error) => {
  console.error("Network error occurred:", error.message);
});

errorBoundary.onGlobalError((error) => {
  console.error("Unexpected error:", error);
});

// Example wrapped function
export const safeProcessUser = errorBoundary.wrap(async (userData: unknown) => {
  const validationResult = validateUser(userData);
  
  if (isErr(validationResult)) {
    throw new ValidationError("User validation failed", "user", userData);
  }

  const user = validationResult.data;
  const fetchResult = await fetchUser(user.id);
  
  if (isErr(fetchResult)) {
    throw fetchResult.error;
  }

  return fetchResult.data;
});

// ========== Usage Examples ==========
export const errorHandlingExamples = {
  // Result pattern examples
  parseNumber: (str: string) => safeParseInt(str),
  parseJson: (json: string) => safeJsonParse(json),
  
  // Validation examples
  validUser: validateUser({
    id: "123",
    name: "John Doe",
    email: "john@example.com",
    age: "30"
  }),
  
  invalidUser: validateUser({
    id: "",
    name: "J",
    email: "invalid-email",
    age: "200"
  }),
  
  // Error boundary
  errorBoundary,
  
  // Type guards
  typeChecks: {
    isString: isString("hello"),
    isNumber: isNumber(42),
    hasProperty: hasProperty({ name: "test" }, "name"),
  }
};