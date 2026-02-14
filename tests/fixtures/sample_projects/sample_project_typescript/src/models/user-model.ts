/**
 * User model accessed via @models/user-model alias
 */

export interface UserModel {
  id: number;
  username: string;
  email: string;
  isActive: boolean;
}

export function createUser(id: number, username: string, email: string): UserModel {
  return { id, username, email, isActive: true };
}

export function deactivateUser(user: UserModel): UserModel {
  return { ...user, isActive: false };
}
