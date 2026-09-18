/**
 * Account module feature root (frontend.instructions.md - colocate this feature's
 * components/hooks/types here, not scattered across the tree).
 *
 * Username/mobile/email + PIN login and registration. Session is an HttpOnly cookie set by the
 * backend (`api/auth.py`) - `AuthProvider`/`useAuth` expose the derived sign-in state to the rest
 * of the app (e.g. `components/layout/Header.tsx`).
 */

export { AuthProvider, useAuth } from './AuthContext';
export { AuthLayout } from './AuthLayout';
export { GuestOnly, RequireAuth } from './AuthRoute';
export { LoginForm } from './LoginForm';
export { RegisterForm } from './RegisterForm';
