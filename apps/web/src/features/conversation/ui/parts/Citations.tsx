import { useTranslation } from 'react-i18next';

import { BookIcon, CaretRightIcon } from '@/shared/ui';

import { useMessage } from '../../model/message-context';

/** The policy clauses the answer cites, as `clause_id@version` with the excerpt in the conversation's language. */
export function Citations() {
  const { t } = useTranslation();
  const { message } = useMessage();
  if (message.citations.length === 0) {
    return null;
  }
  return (
    <details className="group rounded-control text-small">
      <summary className="inline-flex cursor-pointer items-center gap-1.5 rounded-control text-fg-secondary hover:text-fg">
        <CaretRightIcon aria-hidden="true" size={14} className="group-open:rotate-90" />
        <BookIcon aria-hidden="true" size={16} />
        {t('parts.citations.title', { count: message.citations.length })}
      </summary>
      <ul className="mt-2 flex flex-col gap-3 border-l-2 border-border pl-3">
        {message.citations.map((citation) => (
          <li key={citation.clause} className="flex flex-col gap-1">
            <span className="font-mono text-caption text-fg-muted">{citation.clause}</span>
            <span className="whitespace-pre-line text-fg-secondary">{citation.excerpt}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}
