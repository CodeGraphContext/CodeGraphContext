/**
 * Async and Promises
 * Demonstrates TypeScript's asynchronous programming features including
 * promises, async/await, error handling, concurrent operations, and patterns
 */

// ========== Basic Promises ==========
export function createPromise<T>(value: T, delay: number = 100): Promise<T> {
  return new Promise((resolve) => {
    setTimeout(() => resolve(value), delay);
  });
}

export function createRejectedPromise(error: string, delay: number = 100): Promise<never> {
  return new Promise((_, reject) => {
    setTimeout(() => reject(new Error(error)), delay);
  });
}

// ========== Async Functions ==========
export async function fetchUserData(id: number): Promise<{ id: number; name: string; email: string }> {
  // Simulate API call
  await new Promise(resolve => setTimeout(resolve, 200));
  
  if (id <= 0) {
    throw new Error("Invalid user ID");
  }
  
  return {
    id,
    name: `User ${id}`,
    email: `user${id}@example.com`
  };
}

export async function fetchUserPosts(userId: number): Promise<{ id: number; title: string; content: string }[]> {
  await new Promise(resolve => setTimeout(resolve, 150));
  
  return Array.from({ length: 3 }, (_, index) => ({
    id: index + 1,
    title: `Post ${index + 1} by User ${userId}`,
    content: `This is the content of post ${index + 1}`
  }));
}

// ========== Error Handling with Async/Await ==========
export async function safeAsyncOperation<T>(
  operation: () => Promise<T>
): Promise<{ success: true; data: T } | { success: false; error: string }> {
  try {
    const data = await operation();
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error"
    };
  }
}

export async function retryOperation<T>(
  operation: () => Promise<T>,
  maxRetries: number = 3,
  delay: number = 1000
): Promise<T> {
  let lastError: Error;
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      
      if (attempt === maxRetries) {
        throw lastError;
      }
      
      // Exponential backoff
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, attempt - 1)));
    }
  }
  
  throw lastError!;
}

// ========== Promise Combinators ==========
export async function processInParallel<T>(
  items: T[],
  processor: (item: T) => Promise<any>,
  concurrency: number = 3
): Promise<any[]> {
  const results: any[] = [];
  const chunks: T[][] = [];
  
  // Split into chunks
  for (let i = 0; i < items.length; i += concurrency) {
    chunks.push(items.slice(i, i + concurrency));
  }
  
  // Process chunks sequentially, items within chunks in parallel
  for (const chunk of chunks) {
    const chunkResults = await Promise.all(chunk.map(processor));
    results.push(...chunkResults);
  }
  
  return results;
}

export async function raceWithTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number
): Promise<T> {
  const timeoutPromise = new Promise<never>((_, reject) => {
    setTimeout(() => reject(new Error(`Operation timed out after ${timeoutMs}ms`)), timeoutMs);
  });
  
  return Promise.race([promise, timeoutPromise]);
}

// ========== Async Iterators and Generators ==========
export async function* asyncGenerator(count: number): AsyncGenerator<number, void, unknown> {
  for (let i = 0; i < count; i++) {
    await new Promise(resolve => setTimeout(resolve, 100));
    yield i;
  }
}

export async function* fetchDataStream(urls: string[]): AsyncGenerator<string, void, unknown> {
  for (const url of urls) {
    // Simulate fetching data
    await new Promise(resolve => setTimeout(resolve, 200));
    yield `Data from ${url}`;
  }
}

export async function consumeAsyncGenerator<T>(generator: AsyncGenerator<T>): Promise<T[]> {
  const results: T[] = [];
  for await (const item of generator) {
    results.push(item);
  }
  return results;
}

// ========== Observable Pattern ==========
export class EventEmitter<T> {
  private listeners: ((data: T) => void)[] = [];
  private asyncListeners: ((data: T) => Promise<void>)[] = [];

  subscribe(callback: (data: T) => void): () => void {
    this.listeners.push(callback);
    return () => {
      const index = this.listeners.indexOf(callback);
      if (index > -1) {
        this.listeners.splice(index, 1);
      }
    };
  }

  subscribeAsync(callback: (data: T) => Promise<void>): () => void {
    this.asyncListeners.push(callback);
    return () => {
      const index = this.asyncListeners.indexOf(callback);
      if (index > -1) {
        this.asyncListeners.splice(index, 1);
      }
    };
  }

  emit(data: T): void {
    this.listeners.forEach(callback => callback(data));
    // Fire async listeners but don't wait
    this.asyncListeners.forEach(callback => callback(data).catch(console.error));
  }

  async emitAsync(data: T): Promise<void> {
    this.listeners.forEach(callback => callback(data));
    await Promise.all(this.asyncListeners.map(callback => callback(data)));
  }
}

// ========== Promise Pool ==========
export class PromisePool<T, R> {
  private concurrency: number;
  private tasks: (() => Promise<R>)[] = [];
  private running: number = 0;
  private results: R[] = [];
  private errors: Error[] = [];

  constructor(concurrency: number = 5) {
    this.concurrency = concurrency;
  }

  add(task: () => Promise<R>): void {
    this.tasks.push(task);
  }

  async execute(): Promise<{ results: R[]; errors: Error[] }> {
    return new Promise((resolve) => {
      const executeNext = () => {
        if (this.tasks.length === 0 && this.running === 0) {
          resolve({ results: this.results, errors: this.errors });
          return;
        }

        while (this.running < this.concurrency && this.tasks.length > 0) {
          const task = this.tasks.shift()!;
          this.running++;

          task()
            .then(result => {
              this.results.push(result);
            })
            .catch(error => {
              this.errors.push(error instanceof Error ? error : new Error(String(error)));
            })
            .finally(() => {
              this.running--;
              executeNext();
            });
        }
      };

      executeNext();
    });
  }
}

// ========== Async Cache ==========
export class AsyncCache<K, V> {
  private cache = new Map<K, Promise<V>>();
  private ttl: number;

  constructor(ttlMs: number = 60000) {
    this.ttl = ttlMs;
  }

  async get(key: K, factory: () => Promise<V>): Promise<V> {
    if (this.cache.has(key)) {
      try {
        return await this.cache.get(key)!;
      } catch (error) {
        // Remove failed promise from cache
        this.cache.delete(key);
        throw error;
      }
    }

    const promise = factory();
    this.cache.set(key, promise);

    // Set TTL
    setTimeout(() => {
      this.cache.delete(key);
    }, this.ttl);

    return promise;
  }

  clear(): void {
    this.cache.clear();
  }

  has(key: K): boolean {
    return this.cache.has(key);
  }
}

// ========== Async Semaphore ==========
export class Semaphore {
  private permits: number;
  private waiting: (() => void)[] = [];

  constructor(permits: number) {
    this.permits = permits;
  }

  async acquire(): Promise<void> {
    if (this.permits > 0) {
      this.permits--;
      return;
    }

    return new Promise<void>((resolve) => {
      this.waiting.push(resolve);
    });
  }

  release(): void {
    if (this.waiting.length > 0) {
      const next = this.waiting.shift()!;
      next();
    } else {
      this.permits++;
    }
  }

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    await this.acquire();
    try {
      return await fn();
    } finally {
      this.release();
    }
  }
}

// ========== Worker Pattern ==========
export class TaskQueue<T> {
  private queue: T[] = [];
  private processing = false;
  private processor: (item: T) => Promise<void>;

  constructor(processor: (item: T) => Promise<void>) {
    this.processor = processor;
  }

  enqueue(item: T): void {
    this.queue.push(item);
    if (!this.processing) {
      this.processQueue();
    }
  }

  private async processQueue(): Promise<void> {
    this.processing = true;

    while (this.queue.length > 0) {
      const item = this.queue.shift()!;
      try {
        await this.processor(item);
      } catch (error) {
        console.error("Error processing queue item:", error);
      }
    }

    this.processing = false;
  }

  get length(): number {
    return this.queue.length;
  }

  get isProcessing(): boolean {
    return this.processing;
  }
}

// ========== Stream Processing ==========
export async function processStream<T, R>(
  items: T[],
  transformer: (item: T) => Promise<R>,
  batchSize: number = 10
): Promise<R[]> {
  const results: R[] = [];
  
  for (let i = 0; i < items.length; i += batchSize) {
    const batch = items.slice(i, i + batchSize);
    const batchResults = await Promise.all(batch.map(transformer));
    results.push(...batchResults);
  }
  
  return results;
}

// ========== Usage Examples ==========
export const asyncExamples = {
  // Event emitter
  userEvents: new EventEmitter<{ userId: number; action: string }>(),
  
  // Promise pool
  apiCallPool: new PromisePool<void, any>(3),
  
  // Async cache
  userCache: new AsyncCache<number, { id: number; name: string }>(30000),
  
  // Semaphore for rate limiting
  rateLimiter: new Semaphore(5),
  
  // Task queue
  notificationQueue: new TaskQueue<{ userId: number; message: string }>(async (notification) => {
    console.log(`Sending notification to user ${notification.userId}: ${notification.message}`);
    await new Promise(resolve => setTimeout(resolve, 100));
  }),
};

// ========== Complex Async Operations ==========
export async function fetchUserProfile(userId: number): Promise<{
  user: { id: number; name: string; email: string };
  posts: { id: number; title: string; content: string }[];
}> {
  try {
    // Fetch user and posts in parallel
    const [user, posts] = await Promise.all([
      fetchUserData(userId),
      fetchUserPosts(userId)
    ]);

    return { user, posts };
  } catch (error) {
    throw new Error(`Failed to fetch user profile: ${error}`);
  }
}

export async function batchProcessUsers(userIds: number[]): Promise<any[]> {
  // Use the promise pool to limit concurrent API calls
  const pool = new PromisePool<void, any>(3);
  
  userIds.forEach(id => {
    pool.add(async () => {
      const profile = await fetchUserProfile(id);
      return profile;
    });
  });

  const { results, errors } = await pool.execute();
  
  if (errors.length > 0) {
    console.warn(`${errors.length} errors occurred during batch processing:`, errors);
  }
  
  return results;
}

// Initialize some examples
asyncExamples.userEvents.subscribe((event) => {
  console.log(`User event: ${event.action} for user ${event.userId}`);
});

// Example of using the notification queue
asyncExamples.notificationQueue.enqueue({
  userId: 1,
  message: "Welcome to our platform!"
});

asyncExamples.notificationQueue.enqueue({
  userId: 2,
  message: "Your order has been shipped!"
});