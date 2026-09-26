/**
 * Application shell. Phase 12 adds the providers (TanStack Query, i18n, theme), the router, and the real
 * layouts; until then the shell renders only the product name, a proper noun rather than translatable copy.
 */
export function App() {
  return (
    <main className="flex min-h-dvh items-center justify-center p-6">
      <h1 className="text-2xl font-semibold tracking-tight">Bank Agent</h1>
    </main>
  );
}
