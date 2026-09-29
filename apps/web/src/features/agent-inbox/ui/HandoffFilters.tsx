import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';

import { Button, FilterIcon, Select } from '@/shared/ui';

import { FILTER_OPTIONS, readFilters, type FilterName } from '../model/filters';
import { useInboxLabels } from './labels';

const ORDER: readonly FilterName[] = [
  'status',
  'workflow',
  'priority',
  'reason',
  'language',
  'due',
];

/** One select per filter, written to the URL; "all" removes the filter. */
export function HandoffFilters() {
  const { t } = useTranslation();
  const labels = useInboxLabels();
  const [params, setParams] = useSearchParams();
  const filters = readFilters(params);
  const id = useId();
  const active = Object.keys(filters).length > 0;

  const change = (name: FilterName, value: string) => {
    const next = new URLSearchParams(params);
    if (value === '') {
      next.delete(name);
    } else {
      next.set(name, value);
    }
    setParams(next, { replace: true });
  };

  return (
    <form
      aria-labelledby={`${id}-title`}
      className="flex flex-col gap-3 rounded-card border border-border bg-surface p-4"
      onSubmit={(event) => {
        event.preventDefault();
      }}
    >
      <h2 id={`${id}-title`} className="flex items-center gap-2 text-small font-semibold text-fg">
        <FilterIcon aria-hidden="true" size={16} />
        {t('inbox.filters')}
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-6">
        {ORDER.map((name) => (
          <div key={name} className="flex flex-col gap-1.5">
            <label htmlFor={`${id}-${name}`} className="text-small font-medium text-fg">
              {t(`inbox.filter.${name}`)}
            </label>
            <Select
              id={`${id}-${name}`}
              value={filters[name] ?? ''}
              onChange={(event) => {
                change(name, event.target.value);
              }}
            >
              <option value="">{t('inbox.all')}</option>
              {FILTER_OPTIONS[name].map((value) => (
                <option key={value} value={value}>
                  {labels.value(name, value)}
                </option>
              ))}
            </Select>
          </div>
        ))}
      </div>
      {active && (
        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setParams(new URLSearchParams(), { replace: true });
            }}
          >
            {t('inbox.clearFilters')}
          </Button>
        </div>
      )}
    </form>
  );
}
