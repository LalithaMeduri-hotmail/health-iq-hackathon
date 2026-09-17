import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { AppShell } from '@/components/layout/AppShell';
import { ConsentModal } from '@/components/ConsentModal';
import { ThemeProvider } from '@/components/ThemeProvider';
import { AuthProvider } from '@/features/auth';
import { CONSENT_VERSION, hasCurrentConsent } from '@/lib/consent';
import { HealthProfile } from '@/routes/HealthProfile';
import { Home } from '@/routes/Home';
import { Login } from '@/routes/Login';
import { MealPlanner } from '@/routes/MealPlanner';
import { PrescriptionAnalyzer } from '@/routes/PrescriptionAnalyzer';
import { Register } from '@/routes/Register';
import { ReportComparison } from '@/routes/ReportComparison';

const queryClient = new QueryClient();

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
            {!consentVersion && <ConsentModal onAccept={setConsentVersion} />}

            <AppShell>
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                <Route path="/prescriptions" element={<PrescriptionAnalyzer />} />
                <Route path="/profile" element={<HealthProfile />} />
                <Route path="/comparison" element={<ReportComparison />} />
                <Route path="/meal-plan" element={<MealPlanner />} />
              </Routes>
            </AppShell>
          </AuthProvider>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
