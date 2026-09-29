import { Outlet } from 'react-router';

import { LogoutButton, RequireSession } from '@/features/auth';

import { Preferences } from './Preferences';
import { SkipLink } from './SkipLink';
import { useRouteFocus } from './use-route-focus';
import { Wordmark } from './Wordmark';

/**
 * The customer surface: chat-first and mobile-first. A slim header (product, preferences, sign-out) over one
 * centered column wide enough for the conversation and, on wide screens, the glass box beside it.
 */
export function CustomerLayout() {
  const mainRef = useRouteFocus<HTMLElement>();
  return (
    <RequireSession roles={['customer']}>
      <div className="flex min-h-dvh flex-col bg-canvas">
        <SkipLink />
        <header className="sticky top-0 z-30 border-b border-border bg-surface">
          <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
            <Wordmark to="/" />
            <div className="flex items-center gap-1">
              <Preferences />
              <LogoutButton />
            </div>
          </div>
        </header>
        <main
          id="main"
          ref={mainRef}
          tabIndex={-1}
          className="mx-auto w-full max-w-7xl flex-1 px-4 pt-6 outline-none sm:px-6 sm:pt-8"
        >
          <Outlet />
        </main>
      </div>
    </RequireSession>
  );
}
