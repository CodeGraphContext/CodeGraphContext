/**
 * Shared constants accessed via @shared/constants alias
 */

export const APP_NAME = 'TypeScript Sample';
export const MAX_RETRIES = 3;
export const DEFAULT_TIMEOUT = 5000;

export const HTTP_STATUS = {
  OK: 200,
  NOT_FOUND: 404,
  SERVER_ERROR: 500,
} as const;

export type HttpStatusCode = typeof HTTP_STATUS[keyof typeof HTTP_STATUS];
