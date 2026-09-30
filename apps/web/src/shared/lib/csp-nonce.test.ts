import { afterEach, describe, expect, it } from 'vitest';

import { publishCspNonce } from './csp-nonce';

function withMeta(nonce: string): Document {
  const doc = document.implementation.createHTMLDocument('csp');
  const meta = doc.createElement('meta');
  meta.setAttribute('property', 'csp-nonce');
  meta.setAttribute('nonce', nonce);
  doc.head.append(meta);
  return doc;
}

describe('publishCspNonce', () => {
  afterEach(() => {
    delete window.__webpack_nonce__;
  });

  it('publishes the nonce Caddy rendered into the page for injected style elements', () => {
    const nonce = '6f1c2d0e-9a8b-4c7d-8e6f-5a4b3c2d1e0f';
    expect(publishCspNonce(withMeta(nonce), window)).toBe(nonce);
    expect(window.__webpack_nonce__).toBe(nonce);
  });

  it('ignores the unrendered template text of the development server', () => {
    expect(publishCspNonce(withMeta('{{placeholder `http.request.uuid`}}'), window)).toBeNull();
    expect(window.__webpack_nonce__).toBeUndefined();
  });

  it('does nothing without the meta element', () => {
    expect(publishCspNonce(document.implementation.createHTMLDocument('none'), window)).toBeNull();
  });
});
