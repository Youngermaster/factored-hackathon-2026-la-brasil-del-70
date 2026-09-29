import type { Schema } from '@/shared/api';

/**
 * Inbox filters, kept in the URL search params (shareable, and the back button works). Each one maps to the API's
 * query; `due` is a window turned into `sla_due_before` at request time.
 */
export const WORKFLOWS = ['account_inquiry', 'card_support', 'dispute', 'credit'] as const;
export const PRIORITIES = ['critical', 'high', 'medium', 'low'] as const;
export const STATUSES = ['open', 'claimed', 'resolved'] as const;
export const LANGUAGES = ['es', 'pt', 'en'] as const;
export const DUE_WINDOWS = ['overdue', '1h', '4h', '24h'] as const;
export const REASONS = [
  'human_requested',
  'amount_above_auto_limit',
  'repeat_complainer',
  'legal_or_regulator_mention',
  'distress_signal',
  'clarification_exhausted',
  'tool_failure',
  'verification_mismatch',
  'risk_tier_high',
  'sla_breached',
  'unsupported_needs_human',
  'card_unblock_requested',
  'card_replacement_requested',
  'credit_review_required',
  'eligibility_contested',
  'other',
] as const satisfies readonly Schema<'EscalationReasonCode'>[];

export type DueWindow = (typeof DUE_WINDOWS)[number];

export interface HandoffFilters {
  readonly workflow?: (typeof WORKFLOWS)[number];
  readonly priority?: (typeof PRIORITIES)[number];
  readonly reason?: (typeof REASONS)[number];
  readonly language?: (typeof LANGUAGES)[number];
  readonly status?: (typeof STATUSES)[number];
  readonly due?: DueWindow;
}

export type FilterName = keyof HandoffFilters;

export const FILTER_OPTIONS: Readonly<Record<FilterName, readonly string[]>> = {
  workflow: WORKFLOWS,
  priority: PRIORITIES,
  reason: REASONS,
  language: LANGUAGES,
  status: STATUSES,
  due: DUE_WINDOWS,
};

function pick<T extends string>(value: string | null, allowed: readonly T[]): T | undefined {
  return value !== null && (allowed as readonly string[]).includes(value)
    ? (value as T)
    : undefined;
}

/** Reads the filters from the URL; unknown values are ignored, never sent. */
export function readFilters(params: URLSearchParams): HandoffFilters {
  const filters: Record<string, string> = {};
  for (const [name, allowed] of Object.entries(FILTER_OPTIONS)) {
    const value = pick(params.get(name), allowed);
    if (value !== undefined) {
      filters[name] = value;
    }
  }
  return filters;
}

const WINDOW_MS: Record<DueWindow, number> = {
  overdue: 0,
  '1h': 3_600_000,
  '4h': 4 * 3_600_000,
  '24h': 24 * 3_600_000,
};

/** The API query for a filter set: single values become one-element lists; the due window becomes an instant. */
export function toQuery(filters: HandoffFilters, now: Date) {
  return {
    ...(filters.workflow === undefined ? {} : { workflow: [filters.workflow] }),
    ...(filters.priority === undefined ? {} : { priority: [filters.priority] }),
    ...(filters.reason === undefined ? {} : { reason: [filters.reason] }),
    ...(filters.language === undefined ? {} : { language: [filters.language] }),
    ...(filters.status === undefined ? {} : { status: [filters.status] }),
    ...(filters.due === undefined
      ? {}
      : { sla_due_before: new Date(now.getTime() + WINDOW_MS[filters.due]).toISOString() }),
  };
}
