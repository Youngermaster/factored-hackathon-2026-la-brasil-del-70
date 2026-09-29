import { useTranslation } from 'react-i18next';

import { CaretRightIcon } from '@/shared/ui';

import { useMessage } from '../model/message-context';
import { withoutCitedParagraphs } from '../model/text';

/**
 * The verified reply as plain text. An eligibility answer is the exception: its structured view below says the same
 * policy sentences (the locale copy mirrors the policy pack) and adds the rule behind each reason, so the text moves
 * into a disclosure instead of repeating eleven reasons twice.
 */
export function AnswerText() {
  const { t } = useTranslation();
  const { message } = useMessage();
  const text = withoutCitedParagraphs(message.text, message.citations);
  if (message.eligibility === null || message.eligibility === undefined) {
    return <p className="text-body whitespace-pre-line text-fg">{text}</p>;
  }
  return (
    <details className="group text-small">
      <summary className="inline-flex cursor-pointer items-center gap-1.5 rounded-control text-fg-secondary hover:text-fg">
        <CaretRightIcon aria-hidden="true" size={14} className="group-open:rotate-90" />
        {t('chat.fullText')}
      </summary>
      <p className="mt-2 border-l-2 border-border pl-3 whitespace-pre-line text-fg-secondary">
        {text}
      </p>
    </details>
  );
}
