import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import type { Schema } from '@/shared/api';
import { renderApp } from '@/test/app';
import { axe } from '@/test/axe';
import { apiGet, sessionView } from '@/test/msw/api';
import { startAuthServer } from '@/test/msw/auth';
import { server } from '@/test/msw/server';

type Metrics = Schema<'OutcomeMetrics'>;
const count = (value: number, denominator: number) => ({ count: value, denominator });

function metrics(overrides: Partial<Metrics> = {}): Metrics {
  return {
    cases: 100,
    safe_automated_resolution: count(60, 100),
    automation_attempted: count(80, 100),
    containment: count(70, 100),
    escalation_missed: count(2, 20),
    escalation_unnecessary: count(5, 80),
    unsafe_outcomes: count(1, 100),
    latency_p50_ms: 900,
    latency_p95_ms: 2400,
    cost_per_attempted_case_usd: '0.001',
    cost_per_resolution_usd: '0.002',
    ...overrides,
  };
}

function summary(system: 'baseline_b0' | 'proposed', safe: number): Schema<'EvaluationSummary'> {
  const workflows = (['account_inquiry', 'card_support', 'dispute', 'credit'] as const).map(
    (workflow) => ({ ...metrics({ safe_automated_resolution: count(safe, 100) }), workflow }),
  );
  return {
    schema_version: '1.1.0',
    run_id: 'test-local',
    system,
    generated_at: '2026-09-29T12:00:00Z',
    git_sha: 'abc1234def',
    dataset_version: 'test-v1',
    measurement: 'simulated',
    workflows,
    aggregate: metrics({ safe_automated_resolution: count(safe, 100) }),
    breakdowns: [
      {
        ...metrics({ cases: 60, safe_automated_resolution: count(39, 60) }),
        dimension: 'language',
        value: 'es',
        workflow: null,
      },
      {
        ...metrics({ cases: 40, safe_automated_resolution: count(21, 40) }),
        dimension: 'language',
        value: 'pt',
        workflow: null,
      },
    ],
    failure_table: 'docs/evaluation/runs/test-local/failures.csv',
    notes: [],
  };
}

function serve() {
  startAuthServer({ session: sessionView({ role: 'evaluator' }) });
  server.use(
    apiGet('/v1/eval/summaries', () =>
      HttpResponse.json({ summaries: [summary('baseline_b0', 42), summary('proposed', 60)] }),
    ),
  );
  return renderApp({ path: '/console/dashboard' });
}

describe('administrative dashboard', () => {
  it('shows the proposed system, baseline delta, workflow metrics, slices, and provenance', async () => {
    serve();
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Dashboard administrativo' }),
    ).toBeInTheDocument();
    expect(screen.getByText('+18 pp frente a B0: menú con reglas')).toBeInTheDocument();
    expect(screen.getAllByText('60 %').length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: 'Desempeño por flujo' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Idioma' })).toBeInTheDocument();
    expect(
      screen.getByText(/No representa tráfico ni resultados de producción/),
    ).toBeInTheDocument();
    const comparison = screen.getByRole('table', { name: 'Comparación global de sistemas' });
    expect(within(comparison).getAllByRole('row')).toHaveLength(3);
    expect(await axe(document.body, { rules: { region: { enabled: true } } })).toHaveNoViolations();
  });

  it('changes every metric when the evaluator selects another system', async () => {
    const user = userEvent.setup();
    serve();
    const selector = await screen.findByLabelText('Sistema analizado');
    await user.selectOptions(selector, 'baseline_b0');
    expect(screen.getAllByText('42 %').length).toBeGreaterThan(0);
    expect(selector).toHaveValue('baseline_b0');
  });
});
