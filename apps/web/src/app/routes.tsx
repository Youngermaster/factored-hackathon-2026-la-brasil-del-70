import { Outlet, type RouteObject } from 'react-router';

import { AuthProvider } from '@/features/auth';
import { ConsoleOverviewPage } from '@/pages/console/ConsoleOverviewPage';
import { CustomerHomePage } from '@/pages/customer-home/CustomerHomePage';
import { LoginPage } from '@/pages/login/LoginPage';
import { NotFoundPage } from '@/pages/not-found/NotFoundPage';

import { ConsoleLayout } from './layouts/ConsoleLayout';
import { CustomerLayout } from './layouts/CustomerLayout';
import { PublicHeader } from './PublicHeader';
import { RouteError } from './RouteError';
import type { AppServices } from './services';

/**
 * The route tree. The root route hosts the auth provider (it navigates, so it lives inside the router) and the
 * error boundary; the two layouts guard their areas by role.
 */
export function createRoutes(services: AppServices): RouteObject[] {
  return [
    {
      path: '/',
      element: (
        <AuthProvider channel={services.sessionLoss}>
          <Outlet />
        </AuthProvider>
      ),
      errorElement: <RouteError />,
      children: [
        { path: 'login', element: <LoginPage header={<PublicHeader />} /> },
        {
          element: <CustomerLayout />,
          children: [{ index: true, element: <CustomerHomePage /> }],
        },
        {
          path: 'console',
          element: <ConsoleLayout />,
          children: [{ index: true, element: <ConsoleOverviewPage /> }],
        },
        { path: '*', element: <NotFoundPage /> },
      ],
    },
  ];
}
