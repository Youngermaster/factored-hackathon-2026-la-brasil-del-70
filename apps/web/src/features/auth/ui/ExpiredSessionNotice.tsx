import { useTranslation } from 'react-i18next';

import { ClockIcon, SignOutIcon } from '@/shared/ui';

export type LoginReason = 'expired' | 'signed-out';

/**
 * Why the sign-in screen is showing: the session ended (idle or absolute expiry, or revoked) or the person signed
 * out. Announced on arrival, because the app moved here on its own.
 */
export function SessionNotice({ reason }: { readonly reason: LoginReason }) {
  const { t } = useTranslation();
  if (reason === 'signed-out') {
    return (
      <p
        role="status"
        className="flex items-center gap-2 rounded-card border border-border bg-surface px-4 py-3 text-small text-fg"
      >
        <SignOutIcon aria-hidden="true" size={20} className="shrink-0 text-fg-secondary" />
        {t('auth.signedOut')}
      </p>
    );
  }
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-card border border-border-strong bg-surface px-4 py-4"
    >
      <ClockIcon aria-hidden="true" size={22} className="mt-0.5 shrink-0 text-fg-secondary" />
      <div className="flex flex-col gap-1">
        <p className="text-body font-semibold text-fg">{t('auth.expiredTitle')}</p>
        <p className="text-small text-fg-secondary">{t('auth.expiredBody')}</p>
      </div>
    </div>
  );
}
