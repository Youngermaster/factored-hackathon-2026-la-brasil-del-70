/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "true" shows the demo persona picker (docs/demo/personas.md). */
  readonly VITE_DEMO_MODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
