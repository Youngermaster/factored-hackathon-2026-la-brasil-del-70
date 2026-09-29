import type { Schema } from '@/shared/api';

/** Execution record fixtures for glass box tests, typed from the generated schema. Team-made and synthetic. */
type Customer = Schema<'CustomerTraceRecord'>;
type Staff = Schema<'StaffTraceRecord'>;

export function ruleResult(overrides: Partial<Schema<'RuleResult'>> = {}): Schema<'RuleResult'> {
  return {
    rule_id: 'ACC.as_of_disclosed',
    rule_version: 1,
    passed: true,
    effect: null,
    reason_code: 'as_of_disclosed',
    params: {},
    clause_refs: ['ACC-ALL-1@1'],
    missing_facts: [],
    ...overrides,
  };
}

export function decision(overrides: Partial<Schema<'Decision'>> = {}): Schema<'Decision'> {
  return {
    schema_version: '1.3.0',
    state: 'ANSWER_BALANCE',
    action: null,
    kind: 'allow',
    rule_results: [ruleResult()],
    decisive_rule_ids: [],
    clause_refs: ['ACC-ALL-1@1'],
    policy_pack_version: 'pack-fixture',
    ...overrides,
  };
}

export function customerTraceRecord(overrides: Partial<Customer> = {}): Customer {
  return {
    schema_version: '1.3.0',
    turn_id: 'turn-fixture-1',
    conversation_id: 'conv-fixture-1',
    workflow: { id: 'account_inquiry', version: 1 },
    workflow_before: null,
    recorded_at: '2026-09-29T15:00:00Z',
    channel: 'web_chat',
    language: 'es',
    language_detection: {
      language: 'es',
      confidence: 1,
      candidates: [{ language: 'es', score: 1 }],
      is_mixed: false,
      detector: 'language_detector:lexical@1',
    },
    auth_level: 'otp_verified',
    state_before: 'START',
    state_after: 'BALANCES',
    outcome: 'resolved',
    intent: {
      intent: 'balance_inquiry',
      confidence: 0.8,
      candidates: [],
      below_threshold: false,
      model: 'router:keyword@1',
    },
    decisions: [decision()],
    clause_refs: ['ACC-ALL-1@1', 'ESC-ALL-1@1'],
    tool_calls: [
      {
        sequence: 1,
        tool: 'list_my_balances',
        arguments: {},
        idempotency_key: null,
        status: 'ok',
        error_code: null,
        attempts: 1,
        latency_ms: 5,
        result_summary: 'count_2',
        verification: null,
      },
    ],
    llm_calls: [],
    models: ['router:keyword@1', 'language_detector:lexical@1'],
    prompts: [],
    policy_pack_version: 'pack-fixture',
    latency: { total_ms: 13, stages: { gate: 1, workflow: 6 } },
    token_usage: { input_tokens: 0, output_tokens: 0 },
    cost_usd: '0',
    grounding: { llm_phrasing_used: false, template_id: 'account.balances', violations: [] },
    handoff_ref: null,
    case_refs: [],
    eligibility_assessments: [],
    retrieval: null,
    risk_estimates_used: [],
    ...overrides,
  };
}

export function staffTraceRecord(overrides: Partial<Staff> = {}): Staff {
  const base: Partial<Customer> = customerTraceRecord();
  delete base.risk_estimates_used;
  return {
    ...(base as Omit<Customer, 'risk_estimates_used'>),
    risk_estimates: [],
    risk_tier: 'low',
    trust_events_added: [],
    safety_interventions: [],
    trace_id: 'trace-fixture-1',
    ...overrides,
  };
}

/** A credit turn's assessment, as the execution record keeps it (rule ids and versions, no values). */
export function assessmentRecord(
  overrides: Partial<Schema<'EligibilityAssessmentRecord'>> = {},
): Schema<'EligibilityAssessmentRecord'> {
  return {
    assessment_id: 'asm-fixture-1',
    service: 'eligibility:synthetic@1',
    product_code: 'MX-PL-STANDARD',
    outcome: 'review_required',
    rules: [{ rule_id: 'ELG.credit_score_minimum', rule_version: 1 }],
    review_reasons: ['borderline_risk_interval'],
    missing_facts: [],
    policy_pack_version: 'pack-fixture',
    ...overrides,
  };
}
