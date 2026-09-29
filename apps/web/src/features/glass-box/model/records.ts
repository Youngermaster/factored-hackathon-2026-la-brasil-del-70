import type { Schema } from '@/shared/api';

import type { StaffTraceRecord, TraceRecord } from '../api/trace';

type Decision = Schema<'Decision'>;
type RuleResult = Schema<'RuleResult'>;
type ToolCall = Schema<'ToolCallRecord'>;

export function isStaffRecord(record: TraceRecord): record is StaffTraceRecord {
  return 'risk_estimates' in record;
}

/** A rule that could not be evaluated yet (its facts were missing) is neither passed nor failed. */
export type RuleStatus = 'passed' | 'failed' | 'missing';

export function ruleStatus(rule: RuleResult): RuleStatus {
  if (rule.passed) {
    return 'passed';
  }
  return rule.missing_facts.length > 0 ? 'missing' : 'failed';
}

/**
 * A pre-check: the engine evaluates a state's binding before its handler reads any record (the authentication
 * check before each state, the common rules before routing). Its failures are all missing facts; the same state is
 * evaluated again with the facts, so these failures are not decisions against the customer.
 */
export function isPreCheck(decision: Decision): boolean {
  const failed = decision.rule_results.filter((rule) => !rule.passed);
  return failed.length > 0 && failed.every((rule) => rule.missing_facts.length > 0);
}

export interface RuleCounts {
  readonly passed: number;
  readonly failed: number;
  readonly missing: number;
}

export function countRules(decision: Decision): RuleCounts {
  const counts = { passed: 0, failed: 0, missing: 0 };
  for (const rule of decision.rule_results) {
    counts[ruleStatus(rule)] += 1;
  }
  return counts;
}

/** The router moved the conversation to another workflow in this turn. */
export function switchedWorkflow(record: TraceRecord): boolean {
  return record.workflow_before !== null && record.workflow_before.id !== record.workflow.id;
}

/** Write tools share their name with an action kind; everything else reads. */
const WRITES: ReadonlySet<string> = new Set([
  'create_dispute_case',
  'block_card',
  'submit_credit_application',
]);

export function isWrite(tool: ToolCall): boolean {
  return WRITES.has(tool.tool);
}

export type Tone = 'neutral' | 'understanding' | 'decision' | 'risk';

/** A write is yellow only once its read-back verified it; a failed or mismatched write is red. */
export function toolTone(tool: ToolCall): Tone {
  if (tool.verification !== null) {
    return tool.verification.verified ? 'decision' : 'risk';
  }
  if (tool.status === 'failed' || tool.status === 'rejected_by_allowlist') {
    return 'risk';
  }
  return 'neutral';
}

export function outcomeTone(outcome: Schema<'Outcome'>): Tone {
  return outcome === 'escalated' || outcome === 'refused' ? 'risk' : 'neutral';
}

/** The rule result for an eligibility rule id, if the turn's decisions recorded one. */
export function findRule(record: TraceRecord, ruleId: string): RuleResult | undefined {
  for (const decision of record.decisions) {
    const found = decision.rule_results.find((rule) => rule.rule_id === ruleId);
    if (found !== undefined) {
      return found;
    }
  }
  return undefined;
}

/** Latency stages in the order they happened, largest share first when the order is unknown. */
export function latencyStages(record: TraceRecord): readonly (readonly [string, number])[] {
  return Object.entries(record.latency.stages);
}

const WORKFLOW_IDS = ['account_inquiry', 'card_support', 'dispute', 'credit', 'router'] as const;

/** The workflows (and the router) the console has names for; any other id is shown as recorded. */
export function isWorkflowId(id: string): id is (typeof WORKFLOW_IDS)[number] {
  return (WORKFLOW_IDS as readonly string[]).includes(id);
}
