import { useTranslation } from 'react-i18next';

import { Badge } from '@/shared/ui';

import type { EvaluationSummary } from '../api/summaries';
import { systemCode } from '../model/systems';

/** A system column: its short name (H, B0, B1, P), the published id, and its measurement label, always. */
export function SystemLabel({ summary }: { readonly summary: EvaluationSummary }) {
  const { t } = useTranslation();
  const code = systemCode(summary.system);
  return (
    <span className="flex flex-col items-end gap-1">
      <span className="font-semibold text-fg">
        {code === null ? summary.system : t(`eval.systems.${code}`)}
      </span>
      <span className="font-mono text-caption font-normal text-fg-muted">{summary.system}</span>
      <Badge tone={summary.measurement === 'offline' ? 'neutral' : 'understanding'}>
        {t(`eval.measurement.${summary.measurement}`)}
      </Badge>
    </span>
  );
}
