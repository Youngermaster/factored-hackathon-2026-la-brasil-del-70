import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterAll, afterEach, beforeAll } from 'vitest';

import './axe';
import { server } from './msw/server';

// jsdom has no layout: Radix measures popper content with ResizeObserver (tooltips) and uses pointer capture
// for swipe-to-dismiss (toasts). These no-op stand-ins exist only in tests.
class ResizeObserverStub {
  observe(): void {
    // Nothing to measure without layout.
  }
  unobserve(): void {
    // Nothing to measure without layout.
  }
  disconnect(): void {
    // Nothing to measure without layout.
  }
}
// Tooling tests run in the node environment, which has no DOM at all.
const hasDom = 'document' in globalThis;
if (hasDom) {
  Object.assign(globalThis, { ResizeObserver: ResizeObserverStub });
  Object.assign(Element.prototype, {
    hasPointerCapture: () => false,
    setPointerCapture: () => undefined,
    releasePointerCapture: () => undefined,
    // jsdom does not scroll; the chat scrolls new messages and selected turns into view.
    scrollIntoView: () => undefined,
  });
}

// Any request without a handler fails the test, so no test can reach a real network.
beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
});

afterEach(() => {
  cleanup();
  server.resetHandlers();
  server.events.removeAllListeners();
  if (hasDom) {
    document.documentElement.removeAttribute('data-theme');
    window.localStorage.clear();
  }
});

afterAll(() => {
  server.close();
});
