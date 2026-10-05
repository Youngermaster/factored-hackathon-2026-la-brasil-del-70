import { http, HttpResponse } from 'msw';

import type { Schema } from '@/shared/api';

import { apiGet, problem } from './api';
import { server } from './server';

/**
 * Supervision fixtures typed from the generated API schema: the model inventory with its cards, and the health
 * details (served outside `/v1`, so through a raw handler). Values mirror the committed model cards in shape only.
 */
export function modelInventory(
  overrides: Partial<Schema<'ModelInventory'>> = {},
): Schema<'ModelInventory'> {
  return {
    generated_at: '2026-10-05T15:30:00Z',
    components: [
      {
        component: 'router',
        selected: 'keyword@1',
        served: 'router:keyword@1',
        kind: 'baseline',
        alias: null,
        fell_back: false,
        reason: null,
      },
      {
        component: 'resolver',
        selected: 'rules@1',
        served: 'resolver:rules@1',
        kind: 'baseline',
        alias: null,
        fell_back: false,
        reason: null,
      },
      {
        component: 'risk_estimator',
        selected: 'logreg@champion',
        served: 'risk_estimator:score_band@1',
        kind: 'baseline',
        alias: null,
        fell_back: true,
        reason: 'artifact_not_found',
      },
      {
        component: 'retriever',
        selected: 'bm25@1',
        served: 'retriever:bm25@1',
        kind: 'baseline',
        alias: null,
        fell_back: false,
        reason: null,
      },
    ],
    llm: {
      provider: 'litellm',
      configured: true,
      models: [
        {
          role: 'primary',
          model_id: 'azure/gpt-4.1-mini',
          price_basis: 'verified',
          input_usd_per_million: '0.40',
          output_usd_per_million: '1.60',
          listed_on: '2026-10-05',
        },
        {
          role: 'fallback',
          model_id: 'azure/gpt-4o',
          price_basis: 'unknown_model',
          input_usd_per_million: '4.50',
          output_usd_per_million: '18.00',
          listed_on: null,
        },
      ],
      fallback_enabled: true,
      understanding: true,
      phrasing: false,
      handoff_summary: false,
      daily_budget_usd: '10',
      conversation_budget_usd: '0.50',
      session_token_limit: 200000,
      unverified_price_multiplier: '1.5',
    },
    prompts: [
      { prompt: 'extract_dispute_slots@1', purpose: 'understanding', active: true },
      { prompt: 'phrase_response@1', purpose: 'phrasing', active: false },
      { prompt: 'classify_intent_fallback@1', purpose: 'not_called_by_engine', active: false },
    ],
    policy_pack_version: '2026.09.1',
    workflows_enabled: ['account_inquiry', 'card_support', 'dispute', 'credit'],
    ...overrides,
  };
}

export function modelCard(overrides: Partial<Schema<'ModelCard'>> = {}): Schema<'ModelCard'> {
  return {
    component: 'router',
    model: 'router:keyword@1',
    role: 'default',
    note: null,
    use: null,
    split: 'test',
    sample_size: 601,
    sample_unit: 'items',
    kind: 'provisional',
    metrics: [
      { name: 'macro_f1', value: 0.385, low: 0.299, high: 0.439, unit: 'ratio' },
      { name: 'ece', value: 0.185, low: null, high: null, unit: 'ratio' },
    ],
    source: 'docs/models/router.md',
    report: 'docs/evaluation/router.md',
    generated_at: '2026-09-27T20:09:44Z',
    git_sha: '2c19633',
    ...overrides,
  };
}

const count = (value: number, denominator: number) => ({ count: value, denominator });

export function modelCards(
  overrides: Partial<Schema<'ModelCardSet'>> = {},
): Schema<'ModelCardSet'> {
  return {
    schema_version: '1.0.0',
    measurement: 'offline',
    data: 'synthetic',
    cards: [
      modelCard(),
      modelCard({
        model: 'router:tfidf@986872f0284f',
        role: 'champion',
        metrics: [
          { name: 'macro_f1', value: 0.661, low: 0.575, high: 0.718, unit: 'ratio' },
          { name: 'ece', value: 0.125, low: null, high: null, unit: 'ratio' },
        ],
      }),
    ],
    promotions: [
      {
        decision: 'router_and_resolver_defaults',
        outcome: 'keep_baselines',
        reason: 'overlapping_intervals',
        workflows: ['account_inquiry', 'card_support', 'dispute', 'credit'],
        split: 'dev',
        measurement: 'simulated',
        language_model: 'ollama/qwen2.5:7b-instruct',
        session: 'session_14b',
        source: 'docs/evaluation/results.md',
        rows: [
          {
            run_id: 'dev-local-fixed',
            git_sha: '813a6dc',
            models: ['router:keyword@1', 'resolver:rules@1'],
            served: true,
            cases: 112,
            safe_automated_resolution: count(74, 112),
            unsafe_outcomes: count(0, 112),
            routing_correct: count(104, 112),
            escalation_unnecessary: count(10, 94),
            escalation_missed: count(0, 18),
          },
          {
            run_id: 'dev-local-learned',
            git_sha: '1e8e314',
            models: ['router:tfidf@champion', 'resolver:lgbm@champion'],
            served: false,
            cases: 112,
            safe_automated_resolution: count(75, 112),
            unsafe_outcomes: count(2, 112),
            routing_correct: count(103, 112),
            escalation_unnecessary: count(8, 94),
            escalation_missed: count(0, 18),
          },
        ],
      },
    ],
    ...overrides,
  };
}

export function healthDetails(
  overrides: Partial<Schema<'HealthDetailsResponse'>> = {},
): Schema<'HealthDetailsResponse'> {
  return {
    status: 'normal',
    level: 'L0',
    reasons: [],
    components: {
      llm_primary: 'ok',
      llm_fallback: 'ok',
      llm_budget: 'ok',
      models: 'ok',
      credit_catalog: 'ok',
      database: 'ok',
    },
    checks: { database: 'ok' },
    template_only: false,
    budget_used_ratio: 0.125,
    ...overrides,
  };
}

type Answer<Body> =
  Body | { readonly status: number; readonly slug: 'rate-limited' | 'internal-error' };

/** Serves the inventory, the health details (503 with the same body at L4), and the summaries for supervision. */
export function startSupervisionServer({
  inventory = modelInventory(),
  cards = modelCards(),
  health = healthDetails(),
  summaries = [],
}: {
  inventory?: Answer<Schema<'ModelInventory'>>;
  cards?: Schema<'ModelCardSet'>;
  health?: Schema<'HealthDetailsResponse'>;
  summaries?: Schema<'EvaluationSummary'>[];
} = {}) {
  const calls = { models: 0 };
  server.use(
    apiGet('/v1/eval/models', () => {
      calls.models += 1;
      if ('slug' in inventory) {
        return problem(inventory.status, inventory.slug);
      }
      const body: Schema<'ModelInventoryResponse'> = { inventory, cards };
      return HttpResponse.json(body);
    }),
    http.get('*/health/details', () =>
      HttpResponse.json(health, { status: health.level === 'L4' ? 503 : 200 }),
    ),
    apiGet('/v1/eval/summaries', () => HttpResponse.json({ summaries })),
  );
  return calls;
}
