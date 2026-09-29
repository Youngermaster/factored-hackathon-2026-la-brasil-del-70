import { Preferences } from './layouts/Preferences';
import { SkipLink } from './layouts/SkipLink';
import { Wordmark } from './layouts/Wordmark';

/** The header of pages outside a session (sign-in): the product and the preferences. */
export function PublicHeader() {
  return (
    <>
      <SkipLink />
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <Wordmark to="/login" />
          <Preferences />
        </div>
      </header>
    </>
  );
}
