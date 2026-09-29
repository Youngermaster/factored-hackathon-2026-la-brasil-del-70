import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import type { Schema } from '@/shared/api';
import { renderApp } from '@/test/app';
import { sessionView } from '@/test/msw/api';
import { startAuthServer } from '@/test/msw/auth';
import { assistantMessage, startConversationServer } from '@/test/msw/conversation';

type Outcome = Schema<'EligibilityOutcome'>;

const CASES: readonly {
  outcome: Outcome;
  path: Schema<'ReviewPath'>;
  uncertainty: Schema<'UncertaintyStatement'>;
  button: string;
  language: 'es' | 'pt';
}[] = [
  {
    outcome: 'indicatively_eligible',
    path: 'submit_for_human_review',
    uncertainty: 'indicative_only',
    button: 'Enviar a revisión',
    language: 'es',
  },
  {
    outcome: 'not_eligible',
    path: 'request_human_contact',
    uncertainty: 'indicative_only',
    button: 'Pedir revisión de una persona',
    language: 'es',
  },
  {
    outcome: 'review_required',
    path: 'request_human_contact',
    uncertainty: 'borderline_estimate',
    button: 'Pedir revisão de uma pessoa',
    language: 'pt',
  },
  {
    outcome: 'insufficient_data',
    path: 'provide_missing_information',
    uncertainty: 'missing_information',
    button: 'Pedir revisão de uma pessoa',
    language: 'pt',
  },
];

// Approval wording in the three languages, even negated; the eligibility view must never use it.
const APPROVAL = /aprob|aprov|approv/i;

describe.each(CASES)(
  'the eligibility result $outcome',
  ({ outcome, path, uncertainty, button, language }) => {
    it('states the outcome, reasons, uncertainty, review path, and disclaimer, never as success', async () => {
      startAuthServer({ session: sessionView() });
      const chat = startConversationServer({
        script: [
          {
            message: assistantMessage({
              text: 'Resultado indicativo.',
              language,
              eligibility: {
                outcome,
                reasons: [
                  { reason_code: 'credit_score_meets_minimum', clause: 'ELG-MX-1@1' },
                  { reason_code: 'missing_income', clause: 'ELG-ALL-2@1' },
                ],
                missing_facts: outcome === 'insufficient_data' ? ['monthly_income'] : [],
                uncertainty,
                review_path: path,
                disclaimer: 'indicative_not_an_offer_or_decision',
                synthetic: true,
              },
            }),
            outcome: 'in_progress',
            state: 'EXPLAIN_ELIGIBILITY',
            workflow: { id: 'credit', version: 1 },
          },
          { message: assistantMessage({ text: 'Listo.' }) },
        ],
      });
      renderApp({ path: '/' });
      const box = await screen.findByRole('textbox', { name: 'Tu mensaje' });
      await userEvent.type(box, '¿Soy elegible para un préstamo?{Enter}');

      const card = await screen.findByRole('region', {
        name: language === 'es' ? 'Orientación de elegibilidad' : 'Orientação de elegibilidade',
      });
      expect(card.querySelector(`[data-outcome="${outcome}"]`)).not.toBeNull();
      expect(card.textContent).not.toMatch(APPROVAL);
      // No verified pill, no yellow fill, and no score, probability, or band anywhere in the view.
      expect(card.querySelector('[data-status]')).toBeNull();
      expect(card.innerHTML).not.toMatch(/bg-decision\b/);
      expect(card.textContent).not.toMatch(/%|probab|banda|faixa/i);
      expect(within(card).getByText('ELG-MX-1@1')).toBeInTheDocument();
      expect(within(card).getAllByText(/sintétic/).length).toBeGreaterThan(0);

      await userEvent.click(within(card).getByRole('button', { name: button }));
      await screen.findByText('Listo.');
      expect(chat.sent.at(-1)?.text).toBe(
        language === 'es'
          ? 'Sí, quiero que una persona lo revise'
          : 'Sim, quero que uma pessoa revise',
      );
    });
  },
);
