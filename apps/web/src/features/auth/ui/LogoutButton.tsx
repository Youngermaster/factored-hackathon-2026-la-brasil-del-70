import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { Button, SignOutIcon } from '@/shared/ui';

import { useLogout } from '../api/session';
import { replaceSession } from '../model/cache';

/**
 * Signs out: the server revokes the session and clears the cookie; the app leaves the guarded page first and then
 * forgets the session and every cached record, so the guard never redirects on its own.
 */
export function LogoutButton({ className }: { readonly className?: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const logout = useLogout();
  return (
    <Button
      variant="ghost"
      className={className}
      pending={logout.isPending}
      onClick={() => {
        logout.mutate(undefined, {
          onSettled: () => {
            void Promise.resolve(
              navigate('/login?reason=signed-out', { replace: true, flushSync: true }),
            ).then(() => {
              replaceSession(queryClient, null);
            });
          },
        });
      }}
    >
      <SignOutIcon aria-hidden="true" size={18} />
      {t('auth.logout')}
    </Button>
  );
}
