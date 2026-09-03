/** Vitest global setup: jest-dom matchers plus the jsdom gaps Recharts relies on. */

import '@testing-library/jest-dom/vitest';

// Recharts' ResponsiveContainer measures its parent, which jsdom always reports as 0x0.
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
