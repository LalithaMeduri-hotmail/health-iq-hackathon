/**
 * Shared disclaimer footer (frontend.instructions.md - "every feature view renders the shared
 * Disclaimer component; never hide or omit it").
 */

const DISCLAIMER_TEXT =
  'This is a health information and doctor-collaboration assistant. It does not diagnose, ' +
  'prescribe, or replace clinical judgment. Any medicine alternative or health action must be ' +
  'reviewed by a qualified healthcare professional.';

export function Disclaimer({ text = DISCLAIMER_TEXT }: { text?: string }) {
  return (
    <footer role="contentinfo" style={{ fontSize: '0.8rem', padding: '0.75rem', borderTop: '1px solid #ddd' }}>
      {text}
    </footer>
  );
}
