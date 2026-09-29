import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { Button, EmptyIcon } from '@/shared/ui';

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <main
      id="main"
      className="mx-auto flex min-h-dvh w-full max-w-xl flex-col justify-center gap-6 px-4 py-12"
    >
      <EmptyIcon aria-hidden="true" size={32} className="text-fg-muted" />
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-heading font-semibold tracking-tight text-fg">
          {t('errors.notFoundTitle')}
        </h1>
        <p className="text-body text-fg-secondary">{t('errors.notFoundBody')}</p>
      </div>
      <Button asChild variant="secondary" className="self-start">
        <Link to="/">{t('common.goHome')}</Link>
      </Button>
    </main>
  );
}
