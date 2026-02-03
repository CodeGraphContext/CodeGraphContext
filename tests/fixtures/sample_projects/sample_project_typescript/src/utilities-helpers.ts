/**
 * Utilities and Helpers
 * Demonstrates common utility functions, type helpers, and patterns
 * used in TypeScript projects for enhanced development experience
 */

// ========== String Utilities ==========
export const StringUtils = {
  /**
   * Capitalizes the first letter of a string
   */
  capitalize: (str: string): string => 
    str.charAt(0).toUpperCase() + str.slice(1).toLowerCase(),

  /**
   * Converts string to camelCase
   */
  camelCase: (str: string): string =>
    str.replace(/[-_\s]+(.)?/g, (_, char) => (char ? char.toUpperCase() : '')),

  /**
   * Converts string to kebab-case
   */
  kebabCase: (str: string): string =>
    str.replace(/[A-Z]/g, letter => `-${letter.toLowerCase()}`).replace(/^-/, ''),

  /**
   * Converts string to snake_case
   */
  snakeCase: (str: string): string =>
    str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`).replace(/^_/, ''),

  /**
   * Truncates a string to specified length with ellipsis
   */
  truncate: (str: string, length: number, suffix: string = '...'): string =>
    str.length <= length ? str : str.slice(0, length) + suffix,

  /**
   * Removes extra whitespace and trims
   */
  normalize: (str: string): string =>
    str.replace(/\s+/g, ' ').trim(),

  /**
   * Pluralizes a word (simple English rules)
   */
  pluralize: (word: string, count: number = 2): string => {
    if (count === 1) return word;
    if (word.endsWith('y')) return word.slice(0, -1) + 'ies';
    if (word.endsWith('s') || word.endsWith('x') || word.endsWith('ch') || word.endsWith('sh')) {
      return word + 'es';
    }
    return word + 's';
  }
};

// ========== Array Utilities ==========
export const ArrayUtils = {
  /**
   * Chunks array into smaller arrays of specified size
   */
  chunk: <T>(array: T[], size: number): T[][] => {
    const chunks: T[][] = [];
    for (let i = 0; i < array.length; i += size) {
      chunks.push(array.slice(i, i + size));
    }
    return chunks;
  },

  /**
   * Removes duplicate values from array
   */
  unique: <T>(array: T[]): T[] => [...new Set(array)],

  /**
   * Groups array items by a key function
   */
  groupBy: <T, K extends string | number | symbol>(
    array: T[],
    keyFn: (item: T) => K
  ): Record<K, T[]> => {
    return array.reduce((groups, item) => {
      const key = keyFn(item);
      groups[key] = groups[key] || [];
      groups[key]!.push(item);
      return groups;
    }, {} as Record<K, T[]>);
  },

  /**
   * Flattens nested arrays by one level
   */
  flatten: <T>(array: (T | T[])[]): T[] => array.flat() as T[],

  /**
   * Deeply flattens nested arrays
   */
  flattenDeep: <T>(array: any[]): T[] => {
    return array.reduce((acc, val) => 
      Array.isArray(val) ? acc.concat(ArrayUtils.flattenDeep(val)) : acc.concat(val), []
    );
  },

  /**
   * Shuffles array elements randomly
   */
  shuffle: <T>(array: T[]): T[] => {
    const result = [...array];
    for (let i = result.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [result[i], result[j]] = [result[j]!, result[i]!];
    }
    return result;
  },

  /**
   * Returns random element from array
   */
  sample: <T>(array: T[]): T | undefined => {
    return array[Math.floor(Math.random() * array.length)];
  },

  /**
   * Returns multiple random elements from array
   */
  sampleSize: <T>(array: T[], n: number): T[] => {
    const shuffled = ArrayUtils.shuffle(array);
    return shuffled.slice(0, Math.min(n, array.length));
  }
};

// ========== Object Utilities ==========
export const ObjectUtils = {
  /**
   * Deep clones an object
   */
  deepClone: <T>(obj: T): T => {
    if (obj === null || typeof obj !== 'object') return obj;
    if (obj instanceof Date) return new Date(obj.getTime()) as unknown as T;
    if (obj instanceof Array) return obj.map(item => ObjectUtils.deepClone(item)) as unknown as T;
    if (typeof obj === 'object') {
      const copy = {} as T;
      Object.keys(obj).forEach(key => {
        (copy as any)[key] = ObjectUtils.deepClone((obj as any)[key]);
      });
      return copy;
    }
    return obj;
  },

  /**
   * Merges objects deeply
   */
  deepMerge: <T extends Record<string, any>, U extends Record<string, any>>(
    target: T,
    source: U
  ): T & U => {
    const result = { ...target } as T & U;
    
    Object.keys(source).forEach(key => {
      if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
        if (result[key as keyof (T & U)] && typeof result[key as keyof (T & U)] === 'object') {
          (result as any)[key] = ObjectUtils.deepMerge(
            result[key as keyof (T & U)] as any,
            source[key]
          );
        } else {
          (result as any)[key] = ObjectUtils.deepClone(source[key]);
        }
      } else {
        (result as any)[key] = source[key];
      }
    });
    
    return result;
  },

  /**
   * Picks specified keys from object
   */
  pick: <T extends Record<string, any>, K extends keyof T>(
    obj: T,
    keys: K[]
  ): Pick<T, K> => {
    const result = {} as Pick<T, K>;
    keys.forEach(key => {
      if (key in obj) {
        result[key] = obj[key];
      }
    });
    return result;
  },

  /**
   * Omits specified keys from object
   */
  omit: <T extends Record<string, any>, K extends keyof T>(
    obj: T,
    keys: K[]
  ): Omit<T, K> => {
    const result = { ...obj };
    keys.forEach(key => {
      delete result[key];
    });
    return result as Omit<T, K>;
  },

  /**
   * Gets nested value from object using dot notation
   */
  get: <T>(obj: any, path: string, defaultValue?: T): T | undefined => {
    const keys = path.split('.');
    let result = obj;
    
    for (const key of keys) {
      if (result == null || typeof result !== 'object') {
        return defaultValue;
      }
      result = result[key];
    }
    
    return result !== undefined ? result : defaultValue;
  },

  /**
   * Sets nested value in object using dot notation
   */
  set: (obj: any, path: string, value: any): void => {
    const keys = path.split('.');
    const lastKey = keys.pop()!;
    let current = obj;
    
    for (const key of keys) {
      if (!(key in current) || typeof current[key] !== 'object') {
        current[key] = {};
      }
      current = current[key];
    }
    
    current[lastKey] = value;
  },

  /**
   * Checks if object has nested property
   */
  has: (obj: any, path: string): boolean => {
    const keys = path.split('.');
    let current = obj;
    
    for (const key of keys) {
      if (current == null || typeof current !== 'object' || !(key in current)) {
        return false;
      }
      current = current[key];
    }
    
    return true;
  }
};

// ========== Function Utilities ==========
export const FunctionUtils = {
  /**
   * Debounces function execution
   */
  debounce: <T extends (...args: any[]) => any>(
    fn: T,
    delay: number
  ): ((...args: Parameters<T>) => void) => {
    let timeoutId: NodeJS.Timeout;
    return (...args: Parameters<T>) => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => fn(...args), delay);
    };
  },

  /**
   * Throttles function execution
   */
  throttle: <T extends (...args: any[]) => any>(
    fn: T,
    limit: number
  ): ((...args: Parameters<T>) => void) => {
    let inThrottle: boolean;
    return (...args: Parameters<T>) => {
      if (!inThrottle) {
        fn(...args);
        inThrottle = true;
        setTimeout(() => (inThrottle = false), limit);
      }
    };
  },

  /**
   * Memoizes function results
   */
  memoize: <T extends (...args: any[]) => any>(fn: T): T => {
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
  },

  /**
   * Creates a curried version of function
   */
  curry: <T extends (...args: any[]) => any>(
    fn: T,
    arity: number = fn.length
  ): any => {
    return (...args: any[]) => {
      if (args.length >= arity) {
        return fn(...args);
      }
      return FunctionUtils.curry(fn.bind(null, ...args), arity - args.length);
    };
  },

  /**
   * Composes functions from right to left
   */
  compose: <T>(...fns: Function[]): (arg: T) => any => {
    return (arg: T) => fns.reduceRight((result, fn) => fn(result), arg);
  },

  /**
   * Pipes functions from left to right
   */
  pipe: <T>(...fns: Function[]): (arg: T) => any => {
    return (arg: T) => fns.reduce((result, fn) => fn(result), arg);
  }
};

// ========== Date Utilities ==========
export const DateUtils = {
  /**
   * Formats date to ISO string with timezone
   */
  toISOString: (date: Date): string => date.toISOString(),

  /**
   * Formats date to readable string
   */
  format: (date: Date, locale: string = 'en-US'): string => 
    date.toLocaleDateString(locale),

  /**
   * Gets difference between dates in various units
   */
  diff: (date1: Date, date2: Date, unit: 'days' | 'hours' | 'minutes' | 'seconds' = 'days'): number => {
    const diffMs = Math.abs(date1.getTime() - date2.getTime());
    switch (unit) {
      case 'seconds': return Math.floor(diffMs / 1000);
      case 'minutes': return Math.floor(diffMs / (1000 * 60));
      case 'hours': return Math.floor(diffMs / (1000 * 60 * 60));
      case 'days': return Math.floor(diffMs / (1000 * 60 * 60 * 24));
    }
  },

  /**
   * Adds time to date
   */
  add: (date: Date, amount: number, unit: 'days' | 'hours' | 'minutes' | 'seconds'): Date => {
    const result = new Date(date);
    switch (unit) {
      case 'seconds': result.setSeconds(result.getSeconds() + amount); break;
      case 'minutes': result.setMinutes(result.getMinutes() + amount); break;
      case 'hours': result.setHours(result.getHours() + amount); break;
      case 'days': result.setDate(result.getDate() + amount); break;
    }
    return result;
  },

  /**
   * Checks if date is between two dates
   */
  isBetween: (date: Date, start: Date, end: Date): boolean =>
    date >= start && date <= end,

  /**
   * Gets start of day
   */
  startOfDay: (date: Date): Date => {
    const result = new Date(date);
    result.setHours(0, 0, 0, 0);
    return result;
  },

  /**
   * Gets end of day
   */
  endOfDay: (date: Date): Date => {
    const result = new Date(date);
    result.setHours(23, 59, 59, 999);
    return result;
  }
};

// ========== Number Utilities ==========
export const NumberUtils = {
  /**
   * Clamps number between min and max
   */
  clamp: (value: number, min: number, max: number): number =>
    Math.min(Math.max(value, min), max),

  /**
   * Rounds to specified decimal places
   */
  round: (value: number, decimals: number = 0): number =>
    Math.round(value * Math.pow(10, decimals)) / Math.pow(10, decimals),

  /**
   * Generates random number between min and max
   */
  random: (min: number, max: number): number =>
    Math.random() * (max - min) + min,

  /**
   * Generates random integer between min and max (inclusive)
   */
  randomInt: (min: number, max: number): number =>
    Math.floor(Math.random() * (max - min + 1)) + min,

  /**
   * Checks if number is in range
   */
  inRange: (value: number, min: number, max: number): boolean =>
    value >= min && value <= max,

  /**
   * Converts number to percentage string
   */
  toPercent: (value: number, decimals: number = 2): string =>
    `${NumberUtils.round(value * 100, decimals)}%`,

  /**
   * Formats number with thousands separators
   */
  format: (value: number, locale: string = 'en-US'): string =>
    value.toLocaleString(locale)
};

// ========== Type Utilities ==========
export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

export type DeepRequired<T> = {
  [P in keyof T]-?: T[P] extends object ? DeepRequired<T[P]> : T[P];
};

export type KeysOfType<T, U> = {
  [K in keyof T]: T[K] extends U ? K : never;
}[keyof T];

export type Writeable<T> = {
  -readonly [P in keyof T]: T[P];
};

export type OptionalExcept<T, K extends keyof T> = Partial<T> & Pick<T, K>;

export type RequiredExcept<T, K extends keyof T> = Required<Omit<T, K>> & Partial<Pick<T, K>>;

// ========== Validation Helpers ==========
export const ValidationHelpers = {
  /**
   * Email validation
   */
  isEmail: (value: string): boolean =>
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),

  /**
   * URL validation
   */
  isUrl: (value: string): boolean => {
    try {
      new URL(value);
      return true;
    } catch {
      return false;
    }
  },

  /**
   * UUID validation
   */
  isUuid: (value: string): boolean =>
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value),

  /**
   * Credit card number validation (Luhn algorithm)
   */
  isCreditCard: (value: string): boolean => {
    const num = value.replace(/\D/g, '');
    if (num.length < 13 || num.length > 19) return false;
    
    let sum = 0;
    let isEven = false;
    
    for (let i = num.length - 1; i >= 0; i--) {
      let digit = parseInt(num[i]!);
      
      if (isEven) {
        digit *= 2;
        if (digit > 9) digit -= 9;
      }
      
      sum += digit;
      isEven = !isEven;
    }
    
    return sum % 10 === 0;
  },

  /**
   * Strong password validation
   */
  isStrongPassword: (value: string): boolean => {
    const minLength = value.length >= 8;
    const hasLower = /[a-z]/.test(value);
    const hasUpper = /[A-Z]/.test(value);
    const hasNumber = /\d/.test(value);
    const hasSpecial = /[!@#$%^&*(),.?":{}|<>]/.test(value);
    
    return minLength && hasLower && hasUpper && hasNumber && hasSpecial;
  }
};

// ========== Color Utilities ==========
export const ColorUtils = {
  /**
   * Converts hex to RGB
   */
  hexToRgb: (hex: string): { r: number; g: number; b: number } | null => {
    const match = hex.match(/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i);
    return match ? {
      r: parseInt(match[1]!, 16),
      g: parseInt(match[2]!, 16),
      b: parseInt(match[3]!, 16)
    } : null;
  },

  /**
   * Converts RGB to hex
   */
  rgbToHex: (r: number, g: number, b: number): string => {
    const componentToHex = (c: number) => {
      const hex = c.toString(16);
      return hex.length === 1 ? '0' + hex : hex;
    };
    return `#${componentToHex(r)}${componentToHex(g)}${componentToHex(b)}`;
  },

  /**
   * Lightens a color by percentage
   */
  lighten: (hex: string, percent: number): string => {
    const rgb = ColorUtils.hexToRgb(hex);
    if (!rgb) return hex;
    
    const factor = 1 + percent / 100;
    return ColorUtils.rgbToHex(
      Math.min(255, Math.round(rgb.r * factor)),
      Math.min(255, Math.round(rgb.g * factor)),
      Math.min(255, Math.round(rgb.b * factor))
    );
  }
};

// ========== Performance Utilities ==========
export const PerformanceUtils = {
  /**
   * Measures execution time of a function
   */
  measure: async <T>(fn: () => T | Promise<T>): Promise<{ result: T; duration: number }> => {
    const start = performance.now();
    const result = await fn();
    const end = performance.now();
    return { result, duration: end - start };
  },

  /**
   * Creates a performance timer
   */
  timer: () => {
    const start = performance.now();
    return {
      stop: () => performance.now() - start,
      lap: () => {
        const current = performance.now();
        return current - start;
      }
    };
  },

  /**
   * Batches synchronous operations
   */
  batch: <T, R>(
    items: T[],
    processor: (batch: T[]) => R[],
    batchSize: number = 100
  ): R[] => {
    const results: R[] = [];
    for (let i = 0; i < items.length; i += batchSize) {
      const batch = items.slice(i, i + batchSize);
      results.push(...processor(batch));
    }
    return results;
  }
};

// ========== Usage Examples ==========
export const utilityExamples = {
  // String utilities
  camelCased: StringUtils.camelCase("hello-world-example"),
  kebabCased: StringUtils.kebabCase("HelloWorldExample"),
  truncated: StringUtils.truncate("This is a very long string", 15),
  
  // Array utilities
  chunked: ArrayUtils.chunk([1, 2, 3, 4, 5, 6, 7], 3),
  unique: ArrayUtils.unique([1, 2, 2, 3, 3, 3, 4]),
  grouped: ArrayUtils.groupBy(
    [{ type: 'fruit', name: 'apple' }, { type: 'vegetable', name: 'carrot' }],
    item => item.type
  ),
  
  // Object utilities
  picked: ObjectUtils.pick({ a: 1, b: 2, c: 3 }, ['a', 'c']),
  deepValue: ObjectUtils.get({ user: { profile: { name: 'John' } } }, 'user.profile.name'),
  
  // Function utilities
  debouncedLog: FunctionUtils.debounce((message: string) => console.log(message), 1000),
  memoizedFib: FunctionUtils.memoize((n: number): number => {
    if (n <= 1) return n;
    return utilityExamples.memoizedFib(n - 1) + utilityExamples.memoizedFib(n - 2);
  }),
  
  // Date utilities
  futureDate: DateUtils.add(new Date(), 7, 'days'),
  daysDiff: DateUtils.diff(new Date('2023-12-31'), new Date('2023-01-01')),
  
  // Number utilities
  clamped: NumberUtils.clamp(150, 0, 100),
  rounded: NumberUtils.round(3.14159, 2),
  percentage: NumberUtils.toPercent(0.85),
  
  // Validation
  emailValid: ValidationHelpers.isEmail('user@example.com'),
  strongPassword: ValidationHelpers.isStrongPassword('StrongPass123!'),
  
  // Colors
  rgbColor: ColorUtils.hexToRgb('#ff0000'),
  lighterColor: ColorUtils.lighten('#ff0000', 20)
};

// Initialize some examples
console.log('Utility examples initialized:', {
  camelCased: utilityExamples.camelCased,
  chunked: utilityExamples.chunked,
  deepValue: utilityExamples.deepValue
});