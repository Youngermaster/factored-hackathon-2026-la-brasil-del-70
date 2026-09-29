import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { CheckIcon, CopyIcon } from '@/shared/ui';

/**
 * An example message with a copy button. The copy state is announced politely; when the clipboard is not
 * available (an insecure context), the text stays selectable.
 */
export function CopyMessage({ text }: { readonly text: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-start justify-between gap-2 rounded-control border border-border bg-surface-sunken px-3 py-2">
      <span className="text-small break-words text-fg select-all">{text}</span>
      <button
        type="button"
        onClick={() => {
          void navigator.clipboard.writeText(text).then(
            () => {
              setCopied(true);
            },
            () => {
              setCopied(false);
            },
          );
        }}
        className="inline-flex shrink-0 items-center gap-1 rounded-control px-1.5 py-0.5 text-caption font-medium text-fg-secondary hover:bg-surface-hover hover:text-fg"
      >
        {copied ? (
          <CheckIcon aria-hidden="true" size={14} />
        ) : (
          <CopyIcon aria-hidden="true" size={14} />
        )}
        <span aria-live="polite">{copied ? t('demo.copied') : t('demo.copy')}</span>
        <span className="sr-only">: {text}</span>
      </button>
    </div>
  );
}
