import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { PatientIdentityDialog } from './PatientIdentityDialog';

vi.mock('@/features/patient-profiles', () => ({
  useActiveProfile: () => ({
    setActiveProfile: vi.fn(),
    profiles: [
      {
        id: 'account-1',
        displayName: 'Demo User',
        relationshipToAccountOwner: 'self',
        isAccountOwnerProfile: true,
        status: 'active',
      },
    ],
  }),
}));

vi.mock('@/features/patient-profiles/api', () => ({
  createPatientProfile: vi.fn().mockResolvedValue({
    data: {
      id: 'pf-new',
      displayName: 'Asha Rao',
      relationshipToAccountOwner: 'child',
      isAccountOwnerProfile: false,
    },
  }),
}));

vi.mock('./api', () => ({
  assignPrescription: vi.fn().mockResolvedValue({ data: { runId: 'run-1', profileId: 'pf-new' } }),
}));

describe('PatientIdentityDialog', () => {
  it('creates a profile for somebody else, assigns the run, and continues', async () => {
    const user = userEvent.setup();
    const onAssigned = vi.fn();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <PatientIdentityDialog
          runId="run-1"
          extractedName="Asha Rao"
          onAssigned={onAssigned}
          onCancel={vi.fn()}
        />
      </QueryClientProvider>,
    );

    expect(screen.getByRole('dialog', { name: 'Who is this prescription for?' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /It is for/ })).not.toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('File it under a separate profile.');
    expect(screen.getByLabelText('Patient name')).toHaveValue('Asha Rao');
    await user.click(screen.getByRole('button', { name: 'Add and continue' }));

    await waitFor(() => expect(onAssigned).toHaveBeenCalledOnce());
  });
});