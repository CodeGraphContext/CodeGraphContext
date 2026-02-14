/**
 * Application service that demonstrates alias imports alongside relative imports.
 * Used to test that the ts_import_resolver correctly resolves both patterns.
 */

// Alias imports (resolved via tsconfig paths)
import { capitalize, slugify } from '@utils/string-helpers';
import { clamp } from '@utils/math-helpers';
import { UserModel, createUser } from '@models/user-model';
import { APP_NAME, MAX_RETRIES, HTTP_STATUS } from '@shared/constants';
import { Logger } from '@shared/logger';

// Relative imports (resolved relative to this file)
import { User } from './types-interfaces';
import { StringUtils } from './utilities-helpers';

// Bare specifier (npm package, should stay as-is)
import 'reflect-metadata';

const logger = new Logger('AppService');

export class AppService {
  private users: UserModel[] = [];

  constructor() {
    logger.info(`${APP_NAME} initialized`);
  }

  addUser(id: number, username: string, email: string): UserModel {
    const user = createUser(id, capitalize(username), email);
    this.users.push(user);
    logger.info(`User ${user.username} added`);
    return user;
  }

  generateSlug(title: string): string {
    return slugify(title);
  }

  getClampedScore(score: number): number {
    return clamp(score, 0, 100);
  }

  getRetryCount(): number {
    return MAX_RETRIES;
  }

  getStatus(): number {
    return HTTP_STATUS.OK;
  }
}
