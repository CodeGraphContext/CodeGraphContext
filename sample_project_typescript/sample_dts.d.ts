export interface User {
  id: number;
  name: string;
}

export type Role = "admin" | "user";

export function getUser(id: number): User;
