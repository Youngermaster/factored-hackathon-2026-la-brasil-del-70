/**
 * The per-response CSP nonce for style elements that libraries inject at runtime.
 *
 * Radix dialogs lock page scroll through react-remove-scroll, which adds a `<style>` element. The production CSP
 * (deploy/caddy/Caddyfile) allows only `style-src 'self' 'nonce-...'`, with a fresh nonce per response that Caddy also
 * writes into `<meta property="csp-nonce" nonce="...">` in index.html. react-style-singleton reads the nonce through
 * get-nonce, which falls back to the global `__webpack_nonce__`, so publishing the meta value there is enough. In
 * development the meta holds the unrendered template text and there is no CSP, so nothing is published.
 */
const NONCE = /^[A-Za-z0-9+/_=-]{16,128}$/;

export function publishCspNonce(doc: Document = document, target: Window = window): string | null {
  const meta = doc.querySelector<HTMLMetaElement>('meta[property="csp-nonce"]');
  // The nonce IDL attribute holds the value once the browser hides the content attribute; jsdom keeps the attribute.
  const property = meta?.nonce ?? '';
  const nonce = property === '' ? (meta?.getAttribute('nonce') ?? '') : property;
  if (!NONCE.test(nonce)) return null;
  target.__webpack_nonce__ = nonce;
  return nonce;
}
