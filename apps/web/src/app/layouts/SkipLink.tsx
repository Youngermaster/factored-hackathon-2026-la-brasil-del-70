import { useTranslation } from 'react-i18next';

export function SkipLink() {
  const { t } = useTranslation();
  return (
    <a
      href="#main"
      className="sr-only z-50 rounded-control bg-action px-4 py-2 text-small font-medium text-action-fg focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
    >
      {t('app.skipToContent')}
    </a>
  );
}
