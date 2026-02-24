/**
 * Simple logger accessed via @shared/logger alias
 */

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export class Logger {
  constructor(private context: string) {}

  debug(message: string): void {
    this.log('debug', message);
  }

  info(message: string): void {
    this.log('info', message);
  }

  warn(message: string): void {
    this.log('warn', message);
  }

  error(message: string): void {
    this.log('error', message);
  }

  private log(level: LogLevel, message: string): void {
    console.log(`[${level.toUpperCase()}] [${this.context}] ${message}`);
  }
}
