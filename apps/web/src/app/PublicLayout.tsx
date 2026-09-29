import { Outlet } from 'react-router';

import { PublicHeader } from './PublicHeader';
import { useRouteFocus } from './layouts/use-route-focus';

/** Pages anyone may read (About, and the demo guide in demo mode): the public header over one reading column. */
export function PublicLayout() {
  const mainRef = useRouteFocus<HTMLElement>();
  return (
    <div className="flex min-h-dvh flex-col bg-canvas">
      <PublicHeader />
      <main
        id="main"
        ref={mainRef}
        tabIndex={-1}
        className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 outline-none sm:px-6 lg:py-14"
      >
        <Outlet />
      </main>
    </div>
  );
}
