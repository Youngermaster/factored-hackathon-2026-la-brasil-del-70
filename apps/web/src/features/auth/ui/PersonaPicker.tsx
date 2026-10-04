import { useTranslation } from 'react-i18next';

import { useLocale } from '@/shared/i18n';
import { cx } from '@/shared/lib/cx';

import { PERSONAS, type Persona } from '../model/personas';

/**
 * Demo personas as a list of buttons: customers, then bank staff, then the customers that only a seed from the full
 * organizer delivery loads (with a note saying so). Each shows what it demonstrates and its country; choosing one
 * opens a challenge right away.
 */
export function PersonaPicker({
  onSelect,
  pendingId,
}: {
  readonly onSelect: (persona: Persona) => void;
  readonly pendingId: string | null;
}) {
  const { t } = useTranslation();
  const { locale } = useLocale();
  const regions = new Intl.DisplayNames([locale], { type: 'region' });
  const groups = [
    {
      key: 'customers',
      label: t('auth.personaCustomers'),
      note: null,
      personas: PERSONAS.filter((p) => p.role === 'customer' && p.fullDeliveryOnly !== true),
    },
    {
      key: 'staff',
      label: t('auth.personaStaff'),
      note: null,
      personas: PERSONAS.filter((p) => p.role !== 'customer'),
    },
    {
      key: 'full',
      label: t('auth.personaFullDelivery'),
      note: t('auth.personaFullDeliveryNote'),
      personas: PERSONAS.filter((p) => p.fullDeliveryOnly === true),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-title font-semibold text-fg">{t('auth.personaHeading')}</h2>
      {groups.map((group) => (
        <section
          key={group.key}
          aria-labelledby={`persona-group-${group.key}`}
          className="flex flex-col gap-3"
        >
          <h3
            id={`persona-group-${group.key}`}
            className="text-small font-semibold text-fg-secondary"
          >
            {group.label}
          </h3>
          {group.note !== null && <p className="text-caption text-fg-muted">{group.note}</p>}
          <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {group.personas.map((persona) => {
              const description = t(`personas.${persona.id}`);
              return (
                <li key={persona.id}>
                  <button
                    type="button"
                    aria-busy={pendingId === persona.id || undefined}
                    disabled={pendingId !== null}
                    onClick={() => {
                      onSelect(persona);
                    }}
                    className={cx(
                      'flex w-full flex-col items-start gap-1 rounded-control border border-border bg-surface px-4 py-3 text-left',
                      'transition-[border-color,background-color] duration-150 hover:border-fg hover:bg-surface-hover',
                      'disabled:cursor-wait disabled:opacity-60',
                    )}
                  >
                    <span className="text-small font-medium text-fg">{description}</span>
                    <span className="flex flex-wrap items-center gap-x-2 text-caption text-fg-muted">
                      <span className="font-mono">{persona.id}</span>
                      {persona.country !== undefined && <span>{regions.of(persona.country)}</span>}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
