/**
 * Decorators and Metadata
 * Demonstrates TypeScript decorators for classes, methods, properties, and parameters
 * Note: Requires experimentalDecorators and emitDecoratorMetadata in tsconfig.json
 * Also requires reflect-metadata package for metadata reflection
 */

import "reflect-metadata";

// ========== Metadata Keys ==========
export const METADATA_KEYS = {
  VALIDATION_RULES: Symbol("validation:rules"),
  ROUTE_INFO: Symbol("route:info"),
  INJECTABLE: Symbol("injectable"),
  CACHE_CONFIG: Symbol("cache:config"),
  LOG_CONFIG: Symbol("log:config"),
  REQUIRED_ROLE: Symbol("required:role"),
  SERIALIZABLE: Symbol("serializable"),
  MAPPED_PROPERTY: Symbol("mapped:property")
};

// ========== Class Decorators ==========
export function Entity(tableName?: string): ClassDecorator {
  return function <T extends Function>(constructor: T) {
    Reflect.defineMetadata("entity:table", tableName || constructor.name.toLowerCase(), constructor);
    return constructor;
  };
}

export function Injectable(): ClassDecorator {
  return function <T extends Function>(constructor: T) {
    Reflect.defineMetadata(METADATA_KEYS.INJECTABLE, true, constructor);
    return constructor;
  };
}

export function Component(config: { selector: string; template?: string }): ClassDecorator {
  return function <T extends Function>(constructor: T) {
    Reflect.defineMetadata("component:config", config, constructor);
    return constructor;
  };
}

export function Serializable(): ClassDecorator {
  return function <T extends Function>(constructor: T) {
    Reflect.defineMetadata(METADATA_KEYS.SERIALIZABLE, true, constructor);
    
    // Add serialize method to prototype if it doesn't exist
    if (!constructor.prototype.serialize) {
      constructor.prototype.serialize = function() {
        const result: any = {};
        const serializableProps = Reflect.getMetadata("serializable:properties", this.constructor) || [];
        
        for (const prop of serializableProps) {
          if (this[prop] !== undefined) {
            result[prop] = this[prop];
          }
        }
        
        return result;
      };
    }
    
    return constructor;
  };
}

// ========== Method Decorators ==========
export function Log(message?: string): MethodDecorator {
  return function (target: any, propertyName: string | symbol, descriptor: PropertyDescriptor) {
    const originalMethod = descriptor.value;
    const className = target.constructor.name;
    
    descriptor.value = function (...args: any[]) {
      console.log(`[${className}.${String(propertyName)}] ${message || 'Method called'} with args:`, args);
      const result = originalMethod.apply(this, args);
      console.log(`[${className}.${String(propertyName)}] Result:`, result);
      return result;
    };
    
    return descriptor;
  };
}

export function Validate(): MethodDecorator {
  return function (target: any, propertyName: string | symbol, descriptor: PropertyDescriptor) {
    const originalMethod = descriptor.value;
    
    descriptor.value = function (...args: any[]) {
      // Get validation rules from metadata
      const rules = Reflect.getMetadata(METADATA_KEYS.VALIDATION_RULES, target, propertyName) || [];
      
      for (const rule of rules) {
        if (!rule.validate(...args)) {
          throw new Error(rule.message);
        }
      }
      
      return originalMethod.apply(this, args);
    };
    
    return descriptor;
  };
}

export function Cache(ttl: number = 60000): MethodDecorator {
  const cache = new Map<string, { value: any; expires: number }>();
  
  return function (target: any, propertyName: string | symbol, descriptor: PropertyDescriptor) {
    const originalMethod = descriptor.value;
    
    descriptor.value = function (...args: any[]) {
      const cacheKey = `${target.constructor.name}.${String(propertyName)}:${JSON.stringify(args)}`;
      const cached = cache.get(cacheKey);
      
      if (cached && Date.now() < cached.expires) {
        console.log(`Cache hit for ${cacheKey}`);
        return cached.value;
      }
      
      const result = originalMethod.apply(this, args);
      cache.set(cacheKey, { value: result, expires: Date.now() + ttl });
      console.log(`Cache set for ${cacheKey}`);
      
      return result;
    };
    
    return descriptor;
  };
}

export function Retry(maxAttempts: number = 3, delay: number = 1000): MethodDecorator {
  return function (target: any, propertyName: string | symbol, descriptor: PropertyDescriptor) {
    const originalMethod = descriptor.value;
    
    descriptor.value = async function (...args: any[]) {
      for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
          return await originalMethod.apply(this, args);
        } catch (error) {
          if (attempt === maxAttempts) {
            throw error;
          }
          
          console.log(`Attempt ${attempt} failed, retrying in ${delay}ms...`);
          await new Promise(resolve => setTimeout(resolve, delay * attempt));
        }
      }
    };
    
    return descriptor;
  };
}

export function RequireRole(role: string): MethodDecorator {
  return function (target: any, propertyName: string | symbol, descriptor: PropertyDescriptor) {
    Reflect.defineMetadata(METADATA_KEYS.REQUIRED_ROLE, role, target, propertyName);
    
    const originalMethod = descriptor.value;
    
    descriptor.value = function (...args: any[]) {
      const userRole = (this as any).currentUserRole;
      const requiredRole = Reflect.getMetadata(METADATA_KEYS.REQUIRED_ROLE, target, propertyName);
      
      if (!userRole || userRole !== requiredRole) {
        throw new Error(`Access denied. Required role: ${requiredRole}, current role: ${userRole}`);
      }
      
      return originalMethod.apply(this, args);
    };
    
    return descriptor;
  };
}

// ========== Property Decorators ==========
export function Column(options?: { name?: string; type?: string; nullable?: boolean }): PropertyDecorator {
  return function (target: any, propertyKey: string | symbol) {
    const columns = Reflect.getMetadata("entity:columns", target.constructor) || [];
    columns.push({
      propertyKey,
      ...options
    });
    Reflect.defineMetadata("entity:columns", columns, target.constructor);
  };
}

export function Required(): PropertyDecorator {
  return function (target: any, propertyKey: string | symbol) {
    const required = Reflect.getMetadata("validation:required", target.constructor) || [];
    required.push(propertyKey);
    Reflect.defineMetadata("validation:required", required, target.constructor);
  };
}

export function MinLength(length: number): PropertyDecorator {
  return function (target: any, propertyKey: string | symbol) {
    const validations = Reflect.getMetadata("validation:rules", target.constructor) || {};
    validations[propertyKey] = validations[propertyKey] || [];
    validations[propertyKey].push({
      type: "minLength",
      value: length,
      message: `${String(propertyKey)} must be at least ${length} characters long`
    });
    Reflect.defineMetadata("validation:rules", validations, target.constructor);
  };
}

export function Max(value: number): PropertyDecorator {
  return function (target: any, propertyKey: string | symbol) {
    const validations = Reflect.getMetadata("validation:rules", target.constructor) || {};
    validations[propertyKey] = validations[propertyKey] || [];
    validations[propertyKey].push({
      type: "max",
      value: value,
      message: `${String(propertyKey)} must not exceed ${value}`
    });
    Reflect.defineMetadata("validation:rules", validations, target.constructor);
  };
}

export function SerializableProperty(alias?: string): PropertyDecorator {
  return function (target: any, propertyKey: string | symbol) {
    const serializableProps = Reflect.getMetadata("serializable:properties", target.constructor) || [];
    serializableProps.push(propertyKey);
    Reflect.defineMetadata("serializable:properties", serializableProps, target.constructor);
    
    if (alias) {
      const aliases = Reflect.getMetadata("serializable:aliases", target.constructor) || {};
      aliases[propertyKey] = alias;
      Reflect.defineMetadata("serializable:aliases", aliases, target.constructor);
    }
  };
}

export function Computed(): PropertyDecorator {
  return function (target: any, propertyKey: string | symbol) {
    const computed = Reflect.getMetadata("computed:properties", target.constructor) || [];
    computed.push(propertyKey);
    Reflect.defineMetadata("computed:properties", computed, target.constructor);
  };
}

// ========== Parameter Decorators ==========
export function Inject(token?: string): ParameterDecorator {
  return function (target: any, propertyKey: string | symbol | undefined, parameterIndex: number) {
    const existingTokens = Reflect.getMetadata("inject:tokens", target) || [];
    existingTokens[parameterIndex] = token;
    Reflect.defineMetadata("inject:tokens", existingTokens, target);
  };
}

export function ValidateParam(validator: (value: any) => boolean, message: string): ParameterDecorator {
  return function (target: any, propertyKey: string | symbol | undefined, parameterIndex: number) {
    const existingRules = Reflect.getMetadata(METADATA_KEYS.VALIDATION_RULES, target, propertyKey) || [];
    existingRules.push({
      parameterIndex,
      validate: (args: any[]) => validator(args[parameterIndex]),
      message
    });
    Reflect.defineMetadata(METADATA_KEYS.VALIDATION_RULES, existingRules, target, propertyKey);
  };
}

// ========== Accessor Decorators ==========
export function Getter(): MethodDecorator {
  return function (target: any, propertyName: string | symbol, descriptor: PropertyDescriptor) {
    Reflect.defineMetadata("accessor:type", "getter", target, propertyName);
    return descriptor;
  };
}

export function Setter(): MethodDecorator {
  return function (target: any, propertyName: string | symbol, descriptor: PropertyDescriptor) {
    Reflect.defineMetadata("accessor:type", "setter", target, propertyName);
    return descriptor;
  };
}

// ========== Utility Functions for Metadata ==========
export class MetadataReader {
  static getClassMetadata<T>(target: any, key: string | symbol): T | undefined {
    return Reflect.getMetadata(key, target);
  }

  static getMethodMetadata<T>(target: any, method: string, key: string | symbol): T | undefined {
    return Reflect.getMetadata(key, target, method);
  }

  static getPropertyMetadata<T>(target: any, property: string, key: string | symbol): T | undefined {
    return Reflect.getMetadata(key, target, property);
  }

  static getAllMethodNames(target: any): string[] {
    const methods: string[] = [];
    let current = target.prototype;
    
    while (current && current !== Object.prototype) {
      const names = Object.getOwnPropertyNames(current);
      for (const name of names) {
        if (name !== 'constructor' && typeof current[name] === 'function' && !methods.includes(name)) {
          methods.push(name);
        }
      }
      current = Object.getPrototypeOf(current);
    }
    
    return methods;
  }

  static getValidationRules(target: any): any {
    return Reflect.getMetadata("validation:rules", target) || {};
  }

  static getInjectableInfo(target: any): boolean {
    return Reflect.getMetadata(METADATA_KEYS.INJECTABLE, target) || false;
  }
}

// ========== Example Classes Using Decorators ==========
@Entity("users")
@Injectable()
@Serializable()
export class User {
  @Column({ name: "id", type: "integer" })
  @Required()
  @SerializableProperty()
  public id!: number;

  @Column({ name: "username", type: "varchar" })
  @Required()
  @MinLength(3)
  @SerializableProperty()
  public username!: string;

  @Column({ name: "email", type: "varchar" })
  @Required()
  @SerializableProperty("emailAddress")
  public email!: string;

  @Column({ name: "age", type: "integer" })
  @Max(120)
  @SerializableProperty()
  public age!: number;

  private password!: string;
  public currentUserRole?: string;

  constructor(id: number, username: string, email: string, age: number) {
    this.id = id;
    this.username = username;
    this.email = email;
    this.age = age;
  }

  @Log("Getting user info")
  @Cache(30000)
  public getInfo(): string {
    return `User: ${this.username} (${this.email})`;
  }

  @Validate()
  public updateAge(
    @ValidateParam((value: number) => value > 0 && value <= 120, "Age must be between 1 and 120")
    newAge: number
  ): void {
    this.age = newAge;
  }

  @RequireRole("admin")
  public deleteUser(): string {
    return `User ${this.username} has been deleted`;
  }

  @Retry(3, 1000)
  public async syncWithExternalService(): Promise<string> {
    // Simulate an operation that might fail
    if (Math.random() > 0.7) {
      throw new Error("External service unavailable");
    }
    return "Sync completed successfully";
  }

  @Computed()
  public get isAdult(): boolean {
    return this.age >= 18;
  }
}

@Component({ selector: "user-service", template: "<div>User Service</div>" })
export class UserService {
  constructor(
    @Inject("userRepository") private userRepo: any,
    @Inject("logger") private logger: any
  ) {}

  @Log("Finding user by ID")
  public async findById(id: number): Promise<User | null> {
    // Simulate database lookup
    await new Promise(resolve => setTimeout(resolve, 100));
    return new User(id, `user${id}`, `user${id}@example.com`, 25);
  }
}

// ========== Validation Engine ==========
export class ValidationEngine {
  static validate(instance: any): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    const constructor = instance.constructor;
    
    // Check required properties
    const required = Reflect.getMetadata("validation:required", constructor) || [];
    for (const prop of required) {
      if (instance[prop] === undefined || instance[prop] === null) {
        errors.push(`${prop} is required`);
      }
    }
    
    // Check validation rules
    const rules = Reflect.getMetadata("validation:rules", constructor) || {};
    for (const [prop, propRules] of Object.entries(rules)) {
      const value = instance[prop];
      for (const rule of (propRules as any[])) {
        if (rule.type === "minLength" && typeof value === "string" && value.length < rule.value) {
          errors.push(rule.message);
        }
        if (rule.type === "max" && typeof value === "number" && value > rule.value) {
          errors.push(rule.message);
        }
      }
    }
    
    return {
      valid: errors.length === 0,
      errors
    };
  }
}

// ========== Usage Examples ==========
export const decoratorExamples = {
  // Create a user instance
  user: new User(1, "john_doe", "john@example.com", 30),
  
  // Validation examples
  validateUser: (user: User) => ValidationEngine.validate(user),
  
  // Metadata reader examples
  getEntityInfo: (target: any) => ({
    tableName: MetadataReader.getClassMetadata(target, "entity:table"),
    columns: MetadataReader.getClassMetadata(target, "entity:columns"),
    isInjectable: MetadataReader.getInjectableInfo(target)
  }),
  
  // Service instance
  userService: new UserService("mockUserRepo", "mockLogger")
};

// Example usage of the decorated user
decoratorExamples.user.currentUserRole = "admin";

// This will use caching
console.log(decoratorExamples.user.getInfo());

// This will validate the parameter
try {
  decoratorExamples.user.updateAge(25);
} catch (error) {
  console.error("Validation error:", error);
}

// Get metadata about the User class
console.log("User metadata:", decoratorExamples.getEntityInfo(User));