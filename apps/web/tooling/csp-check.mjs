// Browser check of a deployed stack's Content Security Policy (deploy/README.md, "Verify"): drives the real SPA behind
// Caddy through every surface in both themes, at desktop and mobile widths (the mobile glass box opens a Radix dialog),
// and fails on any CSP violation, console error, page error, or failed same-origin request. It also checks that the
// session cookie the browser holds is Secure, HttpOnly, SameSite=Strict, and __Host- prefixed. Needs the stack in demo
// mode, seeded. Not part of make check (CLAUDE.md puts browser end-to-end tests out of scope); a deployment check.
//
//   node tooling/csp-check.mjs https://localhost:8443 --ignore-https-errors   # the local TLS mode (Caddy's own CA)
//   node tooling/csp-check.mjs https://demo.example.org
import { chromium } from 'playwright-chromium';

import { say, signIn, signOut } from './screenshots-flows.mjs';

const baseUrl = (process.argv[2] ?? 'https://localhost:8443').replace(/\/$/, '');
const ignoreHTTPSErrors = process.argv.includes('--ignore-https-errors');
const origin = new URL(baseUrl).origin;
const problems = [];
let pages = 0;

async function open(browser, { theme, viewport }) {
  const size = viewport === 'mobile' ? { width: 390, height: 844 } : { width: 1440, height: 900 };
  const context = await browser.newContext({
    viewport: size,
    colorScheme: theme,
    locale: 'es-MX',
    ignoreHTTPSErrors,
  });
  // The listener is injected by the browser (not the page), so the page's CSP does not apply to it.
  await context.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (event) => {
      console.error(
        `CSP violation: ${event.violatedDirective} blocked ${event.blockedURI || 'inline'}`,
      );
    });
  });
  const page = await context.newPage();
  const where = () => `${theme}/${viewport} ${new URL(page.url()).pathname}`;
  page.on('console', (message) => {
    // A rate-limited sign-in (429) is the limiter working, not a page defect; signInPatiently retries it.
    const rateLimited = message.text().includes('status of 429');
    if (message.type() === 'error' && !rateLimited)
      problems.push(`${where()}: console error: ${message.text()}`);
  });
  page.on('pageerror', (error) => problems.push(`${where()}: page error: ${error.message}`));
  page.on('requestfailed', (request) => {
    if (request.url().startsWith(origin))
      problems.push(`${where()}: request failed: ${request.url()}`);
  });
  page.on('load', () => {
    pages += 1;
  });
  return { context, page };
}

async function visit(page, path, ready) {
  await page.goto(`${baseUrl}${path}`);
  await ready(page);
  await page.waitForTimeout(300);
}

// The auth rate limit (10 per minute per address by default) is shared by every sign-in of this run, which all come
// from one address; a refused sign-in waits out the window and tries again instead of failing the check.
async function signInPatiently(page, persona) {
  for (let attempt = 1; ; attempt += 1) {
    try {
      await signIn(page, baseUrl, persona);
      return;
    } catch (error) {
      if (attempt === 4) throw error;
      console.log(`sign-in as ${persona} did not complete (rate limit), retrying in 30 s`);
      await page.waitForTimeout(30_000);
    }
  }
}

const heading = (page) => page.getByRole('heading', { level: 1 }).first().waitFor();

async function checkCookies(context) {
  const session = (await context.cookies(baseUrl)).find(
    (cookie) => cookie.name === '__Host-session',
  );
  if (!session) problems.push('no __Host-session cookie after sign-in');
  else if (
    !session.secure ||
    !session.httpOnly ||
    session.sameSite !== 'Strict' ||
    session.domain.startsWith('.')
  )
    problems.push('the session cookie is not Secure, HttpOnly, SameSite=Strict, host-only');
}

const browser = await chromium.launch();
for (const theme of ['light', 'dark']) {
  for (const viewport of ['desktop', 'mobile']) {
    const customer = await open(browser, { theme, viewport });
    await signInPatiently(customer.page, 'acc-mx-accounts');
    await checkCookies(customer.context);
    await say(customer.page, '¿Cuál es el saldo de mis cuentas?');
    const conversation = new URL(customer.page.url()).searchParams.get('conversation');
    if (viewport === 'mobile') {
      await customer.page.getByRole('button', { name: 'Registro', exact: true }).click();
      await customer.page.getByRole('dialog').waitFor();
      await customer.page.keyboard.press('Escape');
    }
    await visit(customer.page, `/glass-box/${conversation}`, (page) =>
      page.getByRole('article').first().waitFor(),
    );
    await visit(customer.page, '/demo', heading);
    await visit(customer.page, '/about', heading);
    await customer.context.close();

    const agent = await open(browser, { theme, viewport });
    await signInPatiently(agent.page, 'agent-demo-01');
    // A freshly seeded stack has no handoffs yet (the smoke test's conversations do not escalate): the inbox then
    // shows its empty state instead of a table.
    await visit(agent.page, '/console/inbox', (page) =>
      page.getByRole('table').or(page.getByText('No hay traspasos pendientes')).first().waitFor(),
    );
    await visit(agent.page, '/console/credit-applications', (page) =>
      page.getByRole('table').waitFor(),
    );
    // A desktop dialog too (its scroll lock injects a nonced style element): open the review confirmation, then
    // cancel it, so nothing changes.
    await agent.page.getByRole('table').getByRole('link').first().click();
    await heading(agent.page);
    const review = agent.page.getByRole('button', { name: 'Tomar para revisión' });
    if ((await review.count()) > 0) {
      await review.click();
      await agent.page.getByRole('dialog').waitFor();
      await agent.page.keyboard.press('Escape');
    }
    await signOut(agent.page);
    await agent.context.close();

    const evaluator = await open(browser, { theme, viewport });
    await signInPatiently(evaluator.page, 'evaluator-demo-01');
    await visit(evaluator.page, '/console/evaluation', heading);
    await visit(evaluator.page, `/console/traces/${conversation}`, (page) =>
      page.getByRole('article').first().waitFor(),
    );
    await evaluator.context.close();
  }
}
await browser.close();

if (problems.length > 0) {
  console.error(problems.join('\n'));
  console.error(`csp check failed: ${problems.length} problem(s) over ${pages} page loads`);
  process.exit(1);
}
console.log(
  `csp check passed: no CSP violation, console error, or failed request over ${pages} page loads`,
);
