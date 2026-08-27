import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom';

import { ConsentModal } from '@/components/ConsentModal';
import { Disclaimer } from '@/components/Disclaimer';
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
        <nav aria-label="Primary">
          <Link to="/prescriptions">Prescription Analyzer</Link>
          <Link to="/profile">Health Profile</Link>
          <Link to="/comparison">Report Comparison</Link>
          <Link to="/meal-plan">Meal Planner</Link>
        </nav>

        {!consentVersion && <ConsentModal onAccept={setConsentVersion} />}

        <main>
          <Routes>
            <Route path="/" element={<Navigate to="/prescriptions" replace />} />
            <Route path="/prescriptions" element={<PrescriptionAnalyzer />} />
            <Route path="/profile" element={<HealthProfile />} />
            <Route path="/comparison" element={<ReportComparison />} />
            <Route path="/meal-plan" element={<MealPlanner />} />
          </Routes>
        </main>

        <Disclaimer />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
