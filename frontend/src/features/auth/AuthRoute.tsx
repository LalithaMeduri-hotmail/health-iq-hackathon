import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from './AuthContext';

function SessionLoading() {
  return <p role="status">Checking your session...</p>;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { account, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <SessionLoading />;
  }

  return account ? children : <Navigate to="/login?reason=required" state={{ from: location.pathname }} replace />;
}

export function GuestOnly({ children }: { children: ReactNode }) {
  const { account, isLoading } = useAuth();

  if (isLoading) {
    return <SessionLoading />;
  }

  return account ? <Navigate to="/" replace /> : children;
}