import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router';

import { RequireSession } from '@/features/auth';
import { StaffTrace } from '@/features/glass-box';
import { Button, EmptyState, Field, Input, SearchIcon, TraceIcon } from '@/shared/ui';

/** The evaluator's glass box: look a conversation up by its id, then read every record, internals included. */
export function TraceLookupPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { conversationId } = useParams();
  const [value, setValue] = useState(conversationId ?? '');
  return (
    <RequireSession roles={['evaluator']}>
      <div className="flex flex-col gap-6">
        <div className="flex max-w-3xl flex-col gap-2">
          <h1 className="font-display text-heading font-semibold tracking-tight text-fg">
            {t('traces.heading')}
          </h1>
          <p className="text-body text-fg-secondary">{t('traces.intro')}</p>
        </div>
        <form
          role="search"
          className="flex max-w-2xl flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            const id = value.trim();
            if (id !== '') {
              void navigate(`/console/traces/${encodeURIComponent(id)}`);
            }
          }}
        >
          <Field.Root hasHint className="min-w-64 flex-1">
            <Field.Label>{t('traces.label')}</Field.Label>
            <Field.Control>
              <Input
                value={value}
                spellCheck={false}
                autoComplete="off"
                className="font-mono"
                onChange={(event) => {
                  setValue(event.target.value);
                }}
              />
            </Field.Control>
            <Field.Hint>{t('traces.hint')}</Field.Hint>
          </Field.Root>
          <Button type="submit" size="lg" className="mb-7">
            <SearchIcon aria-hidden="true" size={18} />
            {t('traces.submit')}
          </Button>
        </form>
        {conversationId === undefined ? (
          <EmptyState
            icon={TraceIcon}
            title={t('traces.emptyTitle')}
            description={t('traces.emptyBody')}
          />
        ) : (
          <div className="max-w-4xl">
            <StaffTrace key={conversationId} conversationId={conversationId} />
          </div>
        )}
      </div>
    </RequireSession>
  );
}
