/** Codes the chat has copy for; anything else is shown as sent (a new catalog value never breaks the page). */
export const PURPOSES = [
  'general_purpose',
  'debt_consolidation',
  'home_improvement',
  'education',
  'home_purchase',
  'home_construction',
] as const;

export type Purpose = (typeof PURPOSES)[number];

export function isPurpose(value: string): value is Purpose {
  return (PURPOSES as readonly string[]).includes(value);
}

export const REQUIRED_INFORMATION = [
  'declared_monthly_income',
  'property_value',
  'down_payment',
] as const;

export type RequiredInformation = (typeof REQUIRED_INFORMATION)[number];

export function isRequiredInformation(value: string): value is RequiredInformation {
  return (REQUIRED_INFORMATION as readonly string[]).includes(value);
}
