// Screenshots of the product surfaces against the running stack, for visual review (not part of make check;
// CLAUDE.md puts browser end-to-end tests out of scope). Needs the API with DEMO_MODE=true and LLM_PROVIDER=fake on
// the seeded compose PostgreSQL (run `make seed` first: the flows block a card and open a case), and the dev server
// with VITE_DEMO_MODE=true (see apps/web/README.md). Writes PNGs to apps/web/.shots/ (gitignored).
//
//   node tooling/screenshots.mjs [baseUrl]
//   SHOTS_FLOWS=credit-es,card-es node tooling/screenshots.mjs   # only these flows, then the surfaces
//   SHOTS_SURFACES=0 node tooling/screenshots.mjs                # the flows only
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

import { chromium } from 'playwright-chromium';

import { FLOWS, signIn, signOut } from './screenshots-flows.mjs';

const baseUrl = process.argv[2] ?? 'http://127.0.0.1:5173';
const outDir = fileURLToPath(new URL('../.shots/', import.meta.url));
const viewports = { desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } };
const written = [];

async function open(browser, { theme = 'light', viewport = 'desktop', locale = 'es-MX' } = {}) {
  const context = await browser.newContext({
    viewport: viewports[viewport],
    locale,
    colorScheme: theme,
    reducedMotion: 'reduce',
  });
  await context.addInitScript(
    ([chosen, chosenLocale]) => {
      window.localStorage.setItem(
        'bank-agent.preferences.v1',
        JSON.stringify({ theme: chosen, locale: chosenLocale }),
      );
    },
    [theme, locale],
  );
  const page = await context.newPage();
  page.on('pageerror', (error) => {
    console.error('page error:', error.message);
  });
  const shot = async (name, fullPage = true) => {
    const path = `${outDir}${theme}-${viewport}-${name}.png`;
    await page.waitForTimeout(400);
    await page.screenshot({ path, fullPage });
    written.push(path);
  };
  return { context, page, shot };
}

await mkdir(outDir, { recursive: true });
const browser = await chromium.launch();

// 1. One conversation per workflow and language through the real API, with the glass box beside the chat.
const conversations = {};
const only = process.env.SHOTS_FLOWS?.split(',');
for (const flow of FLOWS.filter((item) => only === undefined || only.includes(item.name))) {
  const { context, page, shot } = await open(browser, { locale: flow.locale });
  await signIn(page, baseUrl, flow.persona);
  try {
    await flow.run(page);
  } catch (error) {
    // Keep going: the failing flow's screen is saved for review, and the run reports it.
    console.error(`flow ${flow.name} failed:`, error instanceof Error ? error.message : error);
    await shot(`failed-${flow.name}`, true);
  }
  conversations[flow.name] = new URL(page.url()).searchParams.get('conversation');
  await shot(`chat-${flow.name}`, false);
  await context.close();
}

// 2. Every surface in both themes at desktop and mobile widths.
for (const theme of process.env.SHOTS_SURFACES === '0' ? [] : ['light', 'dark']) {
  for (const viewport of Object.keys(viewports)) {
    const customer = await open(browser, { theme, viewport });
    await signIn(customer.page, baseUrl, 'cre-ar-borderline');
    await customer.page.goto(`${baseUrl}/?conversation=${conversations['credit-es']}`);
    await customer.page.getByRole('heading', { level: 1 }).waitFor();
    await customer.shot('10-chat', viewport === 'mobile');
    if (viewport === 'mobile') {
      await customer.page.getByRole('button', { name: 'Registro', exact: true }).click();
      await customer.page.getByRole('dialog').waitFor();
      await customer.shot('11-glass-box-sheet', false);
      await customer.page.keyboard.press('Escape');
    }
    await customer.page.goto(`${baseUrl}/glass-box/${conversations['credit-es']}`);
    await customer.page.getByRole('article').first().waitFor();
    await customer.shot('12-glass-box');
    await customer.page.goto(`${baseUrl}/demo`);
    await customer.page.getByRole('heading', { level: 1 }).waitFor();
    await customer.shot('13-demo-guide');
    await customer.page.goto(`${baseUrl}/about`);
    await customer.page.getByRole('heading', { level: 1 }).waitFor();
    await customer.shot('14-about');
    await customer.context.close();

    const agent = await open(browser, { theme, viewport });
    await signIn(agent.page, baseUrl, 'agent-demo-01');
    await agent.page.goto(`${baseUrl}/console/inbox`);
    await agent.page.getByRole('table').waitFor();
    await agent.shot('20-inbox');
    await agent.page.getByRole('table').getByRole('link').first().click();
    await agent.page.getByRole('heading', { level: 1 }).waitFor();
    await agent.shot('21-handoff');
    await agent.page.goto(`${baseUrl}/console/credit-applications`);
    await agent.page.getByRole('table').waitFor();
    await agent.shot('22-credit-applications');
    await signOut(agent.page);
    await agent.context.close();

    const evaluator = await open(browser, { theme, viewport });
    await signIn(evaluator.page, baseUrl, 'evaluator-demo-01');
    await evaluator.page.goto(`${baseUrl}/console/evaluation`);
    await evaluator.page.getByRole('heading', { level: 1 }).waitFor();
    await evaluator.shot('30-evaluation');
    await evaluator.page.goto(`${baseUrl}/console/traces/${conversations['credit-es']}`);
    await evaluator.page.getByRole('article').first().waitFor();
    await evaluator.shot('31-evaluator-trace');
    await evaluator.context.close();
  }
}

await browser.close();
console.log(written.join('\n'));
