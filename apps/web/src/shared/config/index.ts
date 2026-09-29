/**
 * Build-time switches, read from Vite's `import.meta.env` in one place. `VITE_DEMO_MODE=true` shows the demo
 * persona picker labeled as demo mode; the API's own `DEMO_MODE` decides whether codes are shown.
 */
export function isDemoMode(): boolean {
  return import.meta.env.VITE_DEMO_MODE === 'true';
}
