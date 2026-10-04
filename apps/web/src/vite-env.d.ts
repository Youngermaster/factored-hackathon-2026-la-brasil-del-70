/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "true" shows the demo persona picker (docs/demo/personas.md). */
  readonly VITE_DEMO_MODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface Window {
  /** The CSP nonce react-style-singleton (through get-nonce) puts on injected style elements (shared/lib/csp-nonce). */
  __webpack_nonce__?: string;
}
