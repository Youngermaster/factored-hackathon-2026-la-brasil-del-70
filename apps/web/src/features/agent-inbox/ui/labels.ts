import { useTranslation } from 'react-i18next';

import type { FilterName } from '../model/filters';

/**
 * Labels for filter values and enum codes shown in the inbox. The keys are built from API enums, so a value the
 * copy does not know yet is shown as its code rather than dropped.
 */
export function useInboxLabels() {
  const { t, i18n } = useTranslation();
  const label = (key: string, fallback: string) =>
    i18n.exists(key) ? String(t(key as never)) : fallback;
  return {
    value: (name: FilterName, value: string) => label(`inbox.values.${name}.${value}`, value),
    workflow: (id: string | null | undefined) =>
      id === null || id === undefined
        ? label('inbox.noWorkflow', '')
        : label(`inbox.values.workflow.${id}`, id),
    code: (group: string, value: string) => label(`inbox.codes.${group}.${value}`, value),
  };
}
