/**
 * Account module domain types, mirrored from `backend/app/models/account.py` and the shared
 * response envelope (frontend.instructions.md - no `any`, explicit types for every API payload).
 */

export interface AccountPublic {
  userId: string;
  username: string;
  mobile: string | null;
  email: string | null;
  displayName: string | null;
}

export interface AuthResult {
  account: AccountPublic;
  expiresIn: number;
}

export interface RegisterInput {
  username: string;
  mobile?: string;
  email?: string;
  pin: string;
  displayName?: string;
}

export interface LoginInput {
  identifier: string;
  pin: string;
}
