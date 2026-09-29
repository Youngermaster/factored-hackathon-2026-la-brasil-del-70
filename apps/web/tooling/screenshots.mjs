// Screenshots of the key screens against the running stack, for visual review (not part of make check; CLAUDE.md
// puts browser end-to-end tests out of scope). Needs the API with DEMO_MODE=true and the dev server with
// VITE_DEMO_MODE=true (see apps/web/README.md). Writes PNGs to apps/web/.shots/ (gitignored).
//
//   node tooling/screenshots.mjs [baseUrl]
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

import { chromium } from 'playwright-chromium';

const baseUrl = process.argv[2] ?? 'http://127.0.0.1:5173';
const outDir = fileURLToPath(new URL('../.shots/', import.meta.url));
const viewports = { desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } };
const themes = ['light', 'dark'];

async function signIn(page, personaName) {
  await page.goto(`${baseUrl}/login`);
  await page.getByRole('button', { name: personaName }).click();
  const code =
    (
      await page
        .getByText(/^\d{6}$/)
        .first()
        .textContent()
    )?.trim() ?? '';
  await page.getByRole('textbox', { name: /Código de verificación|Verification code/ }).fill(code);
  return code;
}

await mkdir(outDir, { recursive: true });
const browser = await chromium.launch();
const written = [];

for (const theme of themes) {
  for (const [viewportName, viewport] of Object.entries(viewports)) {
    const context = await browser.newContext({
      viewport,
      locale: 'es-MX',
      colorScheme: theme,
      reducedMotion: 'reduce',
    });
    await context.addInitScript((chosen) => {
      window.localStorage.setItem(
        'bank-agent.preferences.v1',
        JSON.stringify({ theme: chosen, locale: 'es-MX' }),
      );
    }, theme);
    const page = await context.newPage();
    // Overlays (dialogs, sheets, toasts) are fixed to the viewport, so their shots are viewport-sized.
    const shot = async (name, fullPage = true) => {
      const path = `${outDir}${theme}-${viewportName}-${name}.png`;
      await page.waitForTimeout(300);
      await page.screenshot({ path, fullPage });
      written.push(path);
    };

    await page.goto(`${baseUrl}/login`);
    await page.getByRole('heading', { level: 1 }).waitFor();
    await shot('01-login');

    await signIn(page, /Dos tarjetas activas/);
    await shot('02-code');
    await page.getByRole('button', { name: 'Verificar' }).click();
    await page.getByRole('heading', { name: '¿En qué te ayudamos hoy?' }).waitFor();
    await shot('03-customer-home');

    await page.getByRole('button', { name: 'Confirmar identidad' }).click();
    await page
      .getByRole('dialog')
      .getByText(/^\d{6}$/)
      .waitFor();
    await shot('04-step-up', false);
    const stepUpCode =
      (
        await page
          .getByRole('dialog')
          .getByText(/^\d{6}$/)
          .textContent()
      )?.trim() ?? '';
    await page.getByRole('dialog').getByRole('textbox').fill(stepUpCode);
    await page.getByRole('dialog').getByRole('button', { name: 'Verificar' }).click();
    await page.getByText('Identidad confirmada.', { exact: true }).waitFor();
    await shot('05-stepped-up', false);

    await page.getByRole('button', { name: 'Cerrar sesión' }).click();
    await page.getByText('Cerraste sesión.', { exact: true }).waitFor();
    await shot('06-signed-out');

    await page.goto(`${baseUrl}/login?reason=expired&next=%2F%3Fconversation%3Dc-123`);
    await page.getByText('Tu sesión terminó', { exact: true }).waitFor();
    await shot('07-expired');

    await signIn(page, /Consola de agente/);
    await page.getByRole('button', { name: 'Verificar' }).click();
    await page.getByRole('heading', { name: 'Resumen' }).waitFor();
    await shot('08-console');

    await page.getByRole('button', { name: 'Preferencias' }).click();
    await page.getByRole('dialog', { name: 'Preferencias' }).waitFor();
    await shot('09-preferences', false);
    await context.close();
  }
}

await browser.close();
console.log(written.join('\n'));
