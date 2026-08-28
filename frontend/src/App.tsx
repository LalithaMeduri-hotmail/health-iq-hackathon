import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { AppShell } from '@/components/layout/AppShell';
import { ConsentModal } from '@/components/ConsentModal';
import { HealthProfile } from '@/routes/HealthProfile';
import { MealPlanner } from '@/routes/MealPlanner';
import { PrescriptionAnalyzer } from '@/routes/PrescriptionAnalyzer';
import { ReportComparison } from '@/routes/ReportComparison';

const queryClient = new QueryClient();

export function App() {
  const [consentVersion, setConsentVersion] = useState<string | null>(null);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {!consentVersion && <ConsentModal onAccept={setConsentVersion} />}

        <AppShell>
          <Routes>
            <Route path="/" element={<Navigate to="/prescriptions" replace />} />
            <Route path="/prescriptions" element={<PrescriptionAnalyzer />} />
            <Route path="/profile" element={<HealthProfile />} />
            <Route path="/comparison" element={<ReportComparison />} />
            <Route path="/meal-plan" element={<MealPlanner />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
