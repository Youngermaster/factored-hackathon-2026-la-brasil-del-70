import { useTranslation } from 'react-i18next';

/**
 * Labels for the codes the model inventory and the health details carry (components, metrics, roles, notes,
 * reasons, decisions). The codes come from the API, so one the copy does not know yet is shown as the code itself
 * rather than dropped.
 */
export function useSupervisionLabels() {
  const { t, i18n } = useTranslation();
  const label = (key: string, fallback: string) =>
    i18n.exists(key) ? String(t(key as never)) : fallback;
  return {
    component: (code: string) => label(`supervision.components.${code}`, code),
    metric: (code: string) => label(`supervision.metrics.${code}`, code),
    kind: (code: string) => label(`supervision.models.kinds.${code}`, code),
    fallbackReason: (code: string) => label(`supervision.models.reasons.${code}`, code),
    role: (code: string) => label(`supervision.offline.roles.${code}`, code),
    note: (code: string) => label(`supervision.offline.notes.${code}`, code),
    use: (code: string) => label(`supervision.offline.uses.${code}`, code),
    unit: (code: string) => label(`supervision.offline.units.${code}`, code),
    split: (code: string) => label(`supervision.offline.splits.${code}`, code),
    cardKind: (code: string) => label(`supervision.offline.kinds.${code}`, code),
    decision: (code: string) => label(`supervision.promotion.decisions.${code}`, code),
    outcome: (code: string) => label(`supervision.promotion.outcomes.${code}`, code),
    promotionReason: (code: string) => label(`supervision.promotion.reasons.${code}`, code),
    llmRole: (code: string) => label(`supervision.llm.roles.${code}`, code),
    priceBasis: (code: string) => label(`supervision.llm.bases.${code}`, code),
    purpose: (code: string) => label(`supervision.llm.purposes.${code}`, code),
    level: (code: string) => label(`supervision.live.levels.${code}`, code),
    status: (code: string) => label(`supervision.live.statuses.${code}`, code),
    healthComponent: (code: string) => label(`supervision.live.components.${code}`, code),
    healthState: (code: string) => label(`supervision.live.states.${code}`, code),
    healthReason: (code: string) => label(`supervision.live.reasonCodes.${code}`, code),
  };
}

export type SupervisionLabels = ReturnType<typeof useSupervisionLabels>;
