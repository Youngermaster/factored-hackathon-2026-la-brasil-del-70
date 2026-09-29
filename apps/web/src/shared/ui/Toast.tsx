import { Toast as RadixToast } from 'radix-ui';
import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { cx } from '@/shared/lib/cx';

import { CheckIcon, CloseIcon, WarningIcon } from './icons';
import { ToastContext, type ToastMessage, type ToastTone } from './toast-context';

interface Entry extends ToastMessage {
  readonly id: number;
}

const toneClasses: Record<ToastTone, string> = {
  neutral: 'border-border bg-surface',
  decision: 'border-decision bg-decision-subtle',
  risk: 'border-risk bg-risk-subtle',
};

function ToneIcon({ tone }: { readonly tone: ToastTone }) {
  if (tone === 'decision') {
    return <CheckIcon aria-hidden="true" size={20} className="shrink-0 text-decision-text" />;
  }
  if (tone === 'risk') {
    return <WarningIcon aria-hidden="true" size={20} className="shrink-0 text-risk-text" />;
  }
  return null;
}

/**
 * Radix toasts: announced through a polite live region, paused on hover and focus, dismissable by swipe, Escape,
 * or the close button, and reachable with F8.
 */
export function ToastProvider({
  children,
  duration = 6000,
}: {
  readonly children: ReactNode;
  readonly duration?: number;
}) {
  const { t } = useTranslation();
  const [entries, setEntries] = useState<Entry[]>([]);
  const next = useRef(0);

  const notify = useCallback((message: ToastMessage) => {
    next.current += 1;
    const id = next.current;
    setEntries((current) => [...current, { ...message, id }]);
  }, []);

  const value = useMemo(() => ({ notify }), [notify]);

  return (
    <ToastContext value={value}>
      <RadixToast.Provider duration={duration} label={t('common.notification')}>
        {children}
        {entries.map(({ id, title, description, tone = 'neutral' }) => (
          <RadixToast.Root
            key={id}
            // Failures interrupt (assertive); confirmations wait for a pause (polite).
            type={tone === 'risk' ? 'foreground' : 'background'}
            onOpenChange={(open) => {
              if (!open) {
                setEntries((current) => current.filter((entry) => entry.id !== id));
              }
            }}
            className={cx(
              'flex items-start gap-3 rounded-card border p-4 text-fg animate-panel-in',
              toneClasses[tone],
            )}
          >
            <ToneIcon tone={tone} />
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <RadixToast.Title className="text-small font-semibold">{title}</RadixToast.Title>
              {description !== undefined && (
                <RadixToast.Description className="text-small text-fg-secondary">
                  {description}
                </RadixToast.Description>
              )}
            </div>
            <RadixToast.Close
              aria-label={t('common.close')}
              className="inline-flex size-8 shrink-0 items-center justify-center rounded-control text-fg-secondary hover:bg-surface-hover hover:text-fg"
            >
              <CloseIcon aria-hidden="true" size={18} />
            </RadixToast.Close>
          </RadixToast.Root>
        ))}
        <RadixToast.Viewport
          label={t('common.notifications')}
          className="fixed right-0 bottom-0 z-50 flex w-full max-w-sm flex-col gap-3 p-4 outline-none"
        />
      </RadixToast.Provider>
    </ToastContext>
  );
}
