import { useTranslation } from 'react-i18next';

import { InfoIcon } from '@/shared/ui';

import { useMessage } from '../../model/message-context';

/** System notices the engine attaches (a language question, a re-authentication), set apart from the answer. */
export function Notices() {
  const { t } = useTranslation();
  const { message } = useMessage();
  if (message.notices.length === 0) {
    return null;
  }
  return (
    <ul className="flex flex-col gap-1">
      {message.notices.map((notice) => (
        <li key={notice} className="flex items-start gap-2 text-small text-fg-secondary">
          <InfoIcon aria-hidden="true" size={16} className="mt-0.5 shrink-0" />
          {t(`chat.notices.${notice}`)}
        </li>
      ))}
    </ul>
  );
}
