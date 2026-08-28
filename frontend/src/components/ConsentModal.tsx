/**
 * Blocking consent modal (frontend.instructions.md - "no file leaves the browser before consent").
 */

import { useState } from 'react';

import { Button } from '@/components/ui';

import { Modal } from './ui/Modal';

interface ConsentModalProps {
  onAccept: (consentVersion: string) => void;
}

const CONSENT_VERSION = '2026-08-27';

export function ConsentModal({ onAccept }: ConsentModalProps) {
  const [accepted, setAccepted] = useState(false);

  return (
    <Modal isOpen={!accepted} title="Before you upload" dismissible={false}>
      <p>
        HealthIQ reads prescriptions, lab reports, and health preferences only to help you understand them and
        collaborate with your doctor. We never diagnose, prescribe, or share your data without your consent.
      </p>
      <p>
        Files you upload are analyzed for medicine/lab extraction only, de-identified before any AI processing, and
        never used to make treatment decisions on your behalf.
      </p>
      <Button
        variant="primary"
        onClick={() => {
          setAccepted(true);
          onAccept(CONSENT_VERSION);
        }}
      >
        I understand and consent
      </Button>
    </Modal>
  );
}
