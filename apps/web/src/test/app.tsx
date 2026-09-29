import { render } from '@testing-library/react';
import { createMemoryRouter } from 'react-router';
import { RouterProvider } from 'react-router/dom';

import { AppProviders } from '@/app/AppProviders';
import { createRoutes } from '@/app/routes';
import { createAppServices } from '@/app/services';
import type { AppLocale } from '@/shared/i18n';
import type { ThemePreference } from '@/shared/lib/preferences';

/** Renders the whole app (providers, routes, guards) at `path`, against MSW, in UTC. */
export function renderApp({
  path = '/',
  locale = 'es-MX',
  theme = 'light',
}: { path?: string; locale?: AppLocale; theme?: ThemePreference } = {}) {
  const services = createAppServices({ baseUrl: 'http://localhost' });
  const router = createMemoryRouter(createRoutes(services), { initialEntries: [path] });
  const view = render(
    <AppProviders services={services} locale={locale} theme={theme} timeZone="UTC">
      <RouterProvider router={router} />
    </AppProviders>,
  );
  return { ...view, router, services };
}

/** The current location of a rendered app, as path plus search. */
export function currentPath(router: ReturnType<typeof createMemoryRouter>): string {
  const { pathname, search } = router.state.location;
  return `${pathname}${search}`;
}
