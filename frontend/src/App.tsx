import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { AppShell } from '@/components/layout/AppShell';
import { ConsentModal } from '@/components/ConsentModal';
import { ThemeProvider } from '@/components/ThemeProvider';
import { AuthLayout, AuthProvider, GuestOnly, RequireAuth, useAuth } from '@/features/auth';
import { ActiveProfileProvider } from '@/features/patient-profiles';
import { CONSENT_VERSION, hasCurrentConsent } from '@/lib/consent';
import { HealthProfile } from '@/routes/HealthProfile';
import { Home } from '@/routes/Home';
import { Login } from '@/routes/Login';
import { MealPlanner } from '@/routes/MealPlanner';
import { PrescriptionAnalyzer } from '@/routes/PrescriptionAnalyzer';
import { Profiles } from '@/routes/Profiles';
import { Register } from '@/routes/Register';
import { ReportComparison } from '@/routes/ReportComparison';

const queryClient = new QueryClient();

interface AppRoutesProps {
  consentVersion: string | null;
  onAcceptConsent: (version: string) => void;
}

function AppRoutes({ consentVersion, onAcceptConsent }: AppRoutesProps) {
  const { account, isLoading } = useAuth();

  return (
    <>
      {!isLoading && account && !consentVersion && <ConsentModal onAccept={onAcceptConsent} />}

      <Routes>
        <Route
          path="/login"
          element={
            <GuestOnly>
              <AuthLayout>
                <Login />
              </AuthLayout>
            </GuestOnly>
          }
        />
        <Route
          path="/register"
          element={
            <GuestOnly>
              <AuthLayout>
                <Register />
              </AuthLayout>
            </GuestOnly>
          }
        />
        <Route
          path="*"
          element={
            <AppShell>
              <Routes>
                <Route path="/" element={<Home />} />
                <Route
                  path="/profiles"
                  element={
                    <RequireAuth>
                      <Profiles />
                    </RequireAuth>
                  }
                />
                <Route
                  path="/prescriptions"
                  element={
                    <RequireAuth>
                      <PrescriptionAnalyzer />
                    </RequireAuth>
                  }
                />
                <Route
                  path="/profile"
                  element={
                    <RequireAuth>
                      <HealthProfile />
                    </RequireAuth>
                  }
                />
                <Route
                  path="/comparison"
                  element={
                    <RequireAuth>
                      <ReportComparison />
                    </RequireAuth>
                  }
                />
                <Route
                  path="/meal-plan"
                  element={
                    <RequireAuth>
                      <MealPlanner />
                    </RequireAuth>
                  }
                />
              </Routes>
            </AppShell>
          }
        />
      </Routes>
    </>
  );
}

export function App() {
  const [consentVersion, setConsentVersion] = useState<string | null>(() =>
    hasCurrentConsent() ? CONSENT_VERSION : null,
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        {/* AuthProvider sits inside the router: ending a session navigates to /login. */}
        <BrowserRouter>
          <AuthProvider>
            {/* Patient profiles depend on the session, so this sits inside AuthProvider. */}
            <ActiveProfileProvider>
              <AppRoutes consentVersion={consentVersion} onAcceptConsent={setConsentVersion} />
            </ActiveProfileProvider>
          </AuthProvider>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
