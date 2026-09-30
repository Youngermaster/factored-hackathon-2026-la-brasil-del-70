import { fileURLToPath, URL } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// The dev server proxies API calls so the browser talks to one origin, as it will behind Caddy.
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/v1': { target: apiProxyTarget, changeOrigin: false },
      '/api': { target: apiProxyTarget, changeOrigin: false },
      '/health': { target: apiProxyTarget, changeOrigin: false },
    },
  },
  build: {
    sourcemap: true,
    // Never inline assets as data: URIs (Vite inlines files under 4 KiB by default, such as small font subsets): the
    // production CSP allows fonts and images from 'self' only (deploy/caddy/Caddyfile).
    assetsInlineLimit: 0,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    restoreMocks: true,
    // tokens.test.ts reads tokens.css as text (?raw); other stylesheets stay stubbed in tests.
    css: { include: [/shared\/ui\/tokens\.css/] },
    // make check runs this suite after the Python suites, often on a busy machine. Worker processes (forks)
    // isolate jsdom state; capping them keeps each worker's start well inside Vitest's fixed 90 s start
    // timeout, and the longer test, hook, and teardown timeouts absorb slow runs without skipping anything.
    pool: 'forks',
    maxWorkers: process.env.CI === undefined ? '50%' : 2,
    testTimeout: 20_000,
    hookTimeout: 30_000,
    teardownTimeout: 30_000,
    exclude: ['**/node_modules/**', '**/dist/**', 'tooling/boundaries-fixture/**', '.shots/**'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/test/**',
        'src/main.tsx',
        'src/vite-env.d.ts',
        'src/shared/api/generated/**',
      ],
      reporter: ['text-summary', 'json-summary'],
      thresholds: {
        'src/features/**': { lines: 70 },
      },
    },
  },
});
