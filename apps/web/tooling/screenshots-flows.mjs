// Conversation flows for tooling/screenshots.mjs: one per workflow and language, driven through the real API with
// the seeded demo personas (docs/demo/personas.md) and the phrasings the demo guide lists. Nothing here is a test.

const CODE = /^\d{6}$/;

/** Signs in as a persona from the demo picker; the demo code is shown on screen in demo mode. */
export async function signIn(page, baseUrl, personaId) {
  await page.goto(`${baseUrl}/login`);
  await page.getByRole('button', { name: new RegExp(personaId) }).click();
  const code = (await page.getByText(CODE).first().textContent())?.trim() ?? '';
  await page.getByRole('textbox', { name: /Código de verifica|Verification code/ }).fill(code);
  await page.getByRole('button', { name: /^(Verificar|Verify)$/ }).click();
  await page.waitForURL((url) => !url.pathname.startsWith('/login'));
  await page.getByRole('heading', { level: 1 }).first().waitFor();
}

export async function signOut(page) {
  await page.getByRole('button', { name: /Cerrar sesión|Sair|Sign out/ }).click();
  await page.waitForURL(/\/login/);
}

/** Sends a message and waits until the answer arrives (the composer is writable again). */
export async function say(page, text) {
  const box = page.getByRole('textbox', { name: /Tu mensaje|Sua mensagem|Your message/ });
  await box.fill(text);
  await box.press('Enter');
  await page.waitForTimeout(300);
  await page.waitForFunction(() => document.querySelector('textarea[readonly]') === null);
  await page.waitForTimeout(500);
}

/** Presses a button in the latest answer, then waits for the reply. */
export async function press(page, name) {
  await page.getByRole('button', { name }).last().click();
  await page.waitForTimeout(800);
}

/** Completes an open step-up dialog with the demo code; the chat then continues the pending write. */
export async function stepUp(page) {
  const dialog = page.getByRole('dialog');
  await dialog.getByText(CODE).waitFor();
  const code = (await dialog.getByText(CODE).textContent())?.trim() ?? '';
  await dialog.getByRole('textbox').fill(code);
  await dialog.getByRole('button', { name: /^(Verificar|Verify)$/ }).click();
  await page.waitForTimeout(2000);
}

/** The flows: persona, the UI locale, and the steps. The dispute reads the merchant from the statement it shows. */
export const FLOWS = [
  {
    name: 'account-es',
    persona: 'acc-mx-accounts',
    locale: 'es-MX',
    run: async (page) => say(page, '¿Cuál es el saldo de mis cuentas?'),
  },
  {
    name: 'account-pt',
    persona: 'acc-ar-similar-transfers',
    locale: 'pt-BR',
    run: async (page) => {
      await say(page, 'Qual é a situação da minha transferência?');
      await say(page, 'a primeira');
    },
  },
  {
    name: 'card-es',
    persona: 'crd-mx-two-cards',
    locale: 'es-MX',
    run: async (page) => {
      await say(page, 'Perdí mi tarjeta, bloquéala por favor');
      await say(page, 'la primera');
      await press(page, /^Confirmar$/);
      await stepUp(page);
    },
  },
  {
    name: 'card-pt',
    persona: 'crd-mx-blocked',
    locale: 'pt-BR',
    run: async (page) => {
      await say(page, 'Quero desbloquear meu cartão');
      await say(page, 'o primeiro');
    },
  },
  {
    name: 'dispute-es',
    persona: 'dsp-mx-open-case',
    locale: 'es-MX',
    run: async (page) => say(page, '¿Cómo va mi aclaración?'),
  },
  {
    name: 'dispute-pt',
    persona: 'dsp-co-unrecognized',
    locale: 'pt-BR',
    run: async (page) => {
      await say(page, 'Quero o extrato de maio do meu cartão de crédito');
      const row = page.getByRole('table', { name: 'Movimentações' }).getByRole('row').nth(1);
      const cells = await row.getByRole('cell').allTextContents();
      const merchant = (cells[1] ?? '').replace(/(Débito|Crédito|Sem classificação)$/, '').trim();
      const amount = (cells[3] ?? '').replace(/[^\d.,]/g, '');
      await say(page, `Não reconheço a cobrança de ${merchant} de 31 de maio por ${amount} pesos`);
      await say(page, 'Sim');
      await say(page, 'Não, obrigado');
      // A charge can be disputed once: on a database where it already was, the assistant abstains instead.
      if ((await page.getByRole('button', { name: /^Confirmar$/ }).count()) === 0) {
        return;
      }
      await press(page, /^Confirmar$/);
      await stepUp(page);
    },
  },
  {
    name: 'credit-es',
    persona: 'cre-ar-borderline',
    locale: 'es-AR',
    run: async (page) => {
      await say(page, '¿Soy elegible para un préstamo personal de 500 mil pesos a 12 meses?');
      await press(page, /Pedir revisión de una persona/);
    },
  },
  {
    name: 'credit-pt',
    persona: 'cre-mx-complete',
    locale: 'pt-BR',
    run: async (page) => {
      await say(page, 'Quais cartões de crédito vocês têm?');
      await say(page, 'Sou elegível para um empréstimo pessoal de 50 mil pesos em 24 meses?');
    },
  },
];
