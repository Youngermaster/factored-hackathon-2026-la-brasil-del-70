import { useId } from 'react';
import { useTranslation } from 'react-i18next';

import { cx } from '@/shared/lib/cx';
import { Button, Sheet, TraceIcon } from '@/shared/ui';

import { useCitedExcerpts, useCustomerTrace } from '../api/trace';
import { Legend } from './Legend';
import { TraceBody } from './TraceBody';

/** The customer's glass box for one conversation: the note, the legend, and one record per turn. */
function CustomerTrace({ conversationId }: { readonly conversationId: string | null }) {
  const trace = useCustomerTrace(conversationId);
  const excerpts = useCitedExcerpts(conversationId, true);
  return (
    <>
      <Legend />
      <TraceBody query={trace} view="customer" excerpts={excerpts} />
    </>
  );
}

/**
 * The panel beside the chat on wide screens. It is a named region that can take focus, so keyboard users can
 * scroll it when the page makes it scroll on its own (WCAG 2.1.1).
 */
export function Panel({
  conversationId,
  className,
}: {
  readonly conversationId: string | null;
  readonly className?: string;
}) {
  const { t } = useTranslation();
  const titleId = useId();
  return (
    <div
      role="region"
      aria-labelledby={titleId}
      tabIndex={0}
      className={cx('flex flex-col gap-4 rounded-card', className)}
    >
      <div className="flex flex-col gap-1">
        <h2 id={titleId} className="text-title font-semibold text-fg">
          {t('glass.title')}
        </h2>
        <p className="text-small text-fg-secondary">{t('glass.intro')}</p>
      </div>
      <CustomerTrace conversationId={conversationId} />
    </div>
  );
}

/** The same trace in a sheet, for narrow screens. */
export function SheetTrigger({ conversationId }: { readonly conversationId: string | null }) {
  const { t } = useTranslation();
  return (
    <Sheet.Root>
      <Sheet.Trigger asChild>
        <Button variant="secondary" size="sm">
          <TraceIcon aria-hidden="true" size={16} />
          {t('glass.open')}
        </Button>
      </Sheet.Trigger>
      <Sheet.Content>
        <Sheet.Title>{t('glass.title')}</Sheet.Title>
        <Sheet.Description className="text-small text-fg-secondary">
          {t('glass.intro')}
        </Sheet.Description>
        <CustomerTrace conversationId={conversationId} />
      </Sheet.Content>
    </Sheet.Root>
  );
}

/** The full-width trace on its own route, for the video and for reading a finished conversation. */
export function Standalone({ conversationId }: { readonly conversationId: string }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-6">
      <div className="flex max-w-3xl flex-col gap-2">
        <h1 className="font-display text-heading font-semibold tracking-tight text-fg">
          {t('glass.title')}
        </h1>
        <p className="text-body text-fg-secondary">{t('glass.intro')}</p>
        <p className="text-small text-fg-muted">
          {t('chat.reference')} <span className="font-mono">{conversationId}</span>
        </p>
      </div>
      <div className="max-w-4xl">
        <CustomerTrace conversationId={conversationId} />
      </div>
    </div>
  );
}
