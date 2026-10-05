import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import type { Schema } from '@/shared/api';
import { currentPath, renderApp } from '@/test/app';
import { axe } from '@/test/axe';
import { sessionView } from '@/test/msw/api';
import { startAuthServer } from '@/test/msw/auth';
import { healthDetails, modelInventory, startSupervisionServer } from '@/test/msw/supervision';

type Metrics = Schema<'OutcomeMetrics'>;
const count = (value: number, denominator: number) => ({ count: value, denominator });

function metrics(safe: number): Metrics {
  return {
    cases: 76,
    safe_automated_resolution: count(safe, 76),
    automation_attempted: count(70, 76),
    containment: count(60, 76),
    escalation_missed: count(1, 20),
    escalation_unnecessary: count(3, 56),
    unsafe_outcomes: count(0, 76),
    latency_p50_ms: 900,
    latency_p95_ms: 2400,
    cost_per_attempted_case_usd: '0.0010',
    cost_per_resolution_usd: '0.0020',
  };
}

function summary(system: 'baseline_b0' | 'baseline_b1' | 'proposed', safe: number) {
  const workflows = (['account_inquiry', 'card_support', 'dispute', 'credit'] as const).map(
    (workflow) => ({ ...metrics(safe), workflow }),
  );
  const result: Schema<'EvaluationSummary'> = {
    schema_version: '1.1.0',
    run_id: 'test-local',
    system,
    generated_at: '2026-09-29T20:37:10Z',
    git_sha: '6bc2e9d0000',
    dataset_version: 'test-v1',
    measurement: 'simulated',
    workflows,
    aggregate: {
      ...metrics(safe * 4),
      cases: 304,
      safe_automated_resolution: count(safe * 4, 304),
    },
    breakdowns: [],
    failure_table: null,
    notes: [],
  };
  return result;
}

const SUMMARIES = [summary('baseline_b0', 40), summary('baseline_b1', 10), summary('proposed', 50)];

function serveEvaluator(options: Parameters<typeof startSupervisionServer>[0] = {}) {
  startAuthServer({ session: sessionView({ role: 'evaluator' }) });
  const calls = startSupervisionServer({ summaries: SUMMARIES, ...options });
  const view = renderApp({ path: '/console/supervision' });
  return { calls, ...view };
}

describe('supervision view', () => {
  it('shows who decides, the served models, their evidence, the evaluation, the model, and the level', async () => {
    serveEvaluator();
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Supervisión de modelos y operación' }),
    ).toBeInTheDocument();

    const served = await screen.findByRole('table', { name: 'Componentes y modelo servido' });
    expect(within(served).getAllByText('router:keyword@1').length).toBeGreaterThan(0);
    expect(within(served).getByText('Artefacto no encontrado')).toBeInTheDocument();
    expect(screen.getByText('Modelo de lenguaje azure/gpt-4.1-mini')).toBeInTheDocument();
    expect(screen.getByText('Paquete de políticas 2026.09.1')).toBeInTheDocument();

    expect(screen.getByRole('img', { name: 'F1 macro, intervalo del 95 %' })).toBeInTheDocument();
    const router = screen.getByRole('table', {
      name: 'Enrutador de intención: métricas por modelo',
    });
    expect(within(router).getByText('0.661')).toBeInTheDocument();
    expect(within(router).getByText('0.575 a 0.718')).toBeInTheDocument();
    expect(within(router).getByText('En servicio')).toBeInTheDocument();
    expect(screen.getByText('Provisional')).toBeInTheDocument();

    expect(
      screen.getByText(
        'Resultado: se mantienen las líneas base, porque los intervalos se superponen.',
      ),
    ).toBeInTheDocument();
    const decision = screen.getByRole('table', {
      name: 'Enrutador y resolución de transacciones: configuraciones comparadas',
    });
    expect(within(decision).getByText(/74 de 112/)).toBeInTheDocument();
    expect(within(decision).getByText('2 de 112')).toBeInTheDocument();

    const evaluation = await screen.findByRole('table', {
      name: 'Corrida test-local: resolución automática segura y costo por resolución',
    });
    const rowHeaders = within(evaluation)
      .getAllByRole('rowheader')
      .map((cell) => cell.textContent);
    expect(rowHeaders).toEqual(['Cuentas y pagos', 'Tarjetas', 'Aclaraciones', 'Crédito', 'Total']);
    expect(within(evaluation).getAllByText('B0: menú con reglas').length).toBeGreaterThan(0);
    expect(within(evaluation).getAllByText('P: propuesto').length).toBeGreaterThan(0);

    const models = screen.getByRole('table', { name: 'Modelos configurados y base de precio' });
    expect(within(models).getByText('Verificado')).toBeInTheDocument();
    expect(within(models).getByText('Sin precio, tope con margen')).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Versiones de prompt' })).toBeInTheDocument();

    expect(await screen.findByText('L0: normal')).toBeInTheDocument();
    const grafana = screen.getByRole('link', { name: /Abrir el tablero de Grafana/ });
    expect(grafana).toHaveAttribute('href', '/grafana/');
    expect(grafana).toHaveAttribute('rel', 'noopener noreferrer');

    expect(await axe(document.body, { rules: { region: { enabled: true } } })).toHaveNoViolations();
  });

  it('reads the L4 body of a 503 health answer and keeps the other sections', async () => {
    serveEvaluator({
      health: healthDetails({
        status: 'unavailable',
        level: 'L4',
        reasons: ['database_unavailable'],
        components: {
          llm_primary: 'ok',
          llm_fallback: 'ok',
          llm_budget: 'ok',
          models: 'ok',
          credit_catalog: 'ok',
          database: 'unavailable',
        },
      }),
    });
    expect(await screen.findByText('L4: base de datos no disponible')).toBeInTheDocument();
    expect(screen.getAllByText('Base de datos no disponible').length).toBeGreaterThan(0);
    expect(
      await screen.findByRole('table', { name: 'Componentes y modelo servido' }),
    ).toBeInTheDocument();
  });

  it('shows the request id when the inventory fails and retries on request', async () => {
    const user = userEvent.setup();
    const { calls } = serveEvaluator({ inventory: { status: 429, slug: 'rate-limited' } });
    expect(
      await screen.findByText('No pudimos cargar el inventario de modelos'),
    ).toBeInTheDocument();
    expect(screen.getByText(/req-test-0001/)).toBeInTheDocument();
    expect(await screen.findByText('L0: normal')).toBeInTheDocument();
    const before = calls.models;
    await user.click(screen.getByRole('button', { name: 'Reintentar' }));
    await screen.findByText('No pudimos cargar el inventario de modelos');
    expect(calls.models).toBeGreaterThan(before);
  });

  it('says the deterministic paths answer when no language model is configured', async () => {
    const inventory = modelInventory();
    serveEvaluator({
      inventory: {
        ...inventory,
        llm: {
          ...inventory.llm,
          provider: 'fake',
          configured: false,
          models: [],
          fallback_enabled: false,
        },
        prompts: inventory.prompts.map((use) => ({ ...use, active: false })),
      },
    });
    expect(
      await screen.findByText('Sin modelo configurado: responden las rutas deterministas.'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Sin modelo de lenguaje: responden las rutas deterministas'),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('table', { name: 'Modelos configurados y base de precio' }),
    ).not.toBeInTheDocument();
  });

  it('sends an agent back to the console start', async () => {
    startAuthServer({ session: sessionView({ role: 'agent' }) });
    startSupervisionServer();
    const { router } = renderApp({ path: '/console/supervision' });
    await screen.findByRole('heading', { level: 1, name: 'Resumen' });
    expect(currentPath(router)).toBe('/console');
  });

  it('lists the view in the evaluator sidebar and on the console start', async () => {
    startAuthServer({ session: sessionView({ role: 'evaluator' }) });
    startSupervisionServer();
    renderApp({ path: '/console' });
    const navigation = await screen.findByRole('navigation', { name: 'Navegación de la consola' });
    expect(within(navigation).getByRole('link', { name: 'Supervisión' })).toHaveAttribute(
      'href',
      '/console/supervision',
    );
    expect(screen.getAllByRole('link', { name: /Supervisión/ }).length).toBeGreaterThan(1);
  });
});
