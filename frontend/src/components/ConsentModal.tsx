/**
 * Blocking consent modal (frontend.instructions.md - "no file leaves the browser before consent").
 */

import { useState } from 'react';

interface ConsentModalProps {
  onAccept: (consentVersion: string) => void;
}

const CONSENT_VERSION = '2026-08-27';

export function ConsentModal({ onAccept }: ConsentModalProps) {
  const [accepted, setAccepted] = useState(false);

  if (accepted) {
    return null;
  }

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="consent-title">
      <h2 id="consent-title">Before you upload</h2>
      {/* TODO(D4): full consent copy, purpose limitation, and link to privacy notice. */}
      <button
        type="button"
        onClick={() => {
          setAccepted(true);
          onAccept(CONSENT_VERSION);
        }}
      >
        I understand and consent
      </button>
    </div>
  );
}
