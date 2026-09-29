import { Outlet, type RouteObject } from 'react-router';

import { AuthProvider } from '@/features/auth';
import { LoginPage } from '@/pages/login/LoginPage';
import { NotFoundPage } from '@/pages/not-found/NotFoundPage';

import { ConsoleLayout } from './layouts/ConsoleLayout';
import { CustomerLayout } from './layouts/CustomerLayout';
import { PublicHeader } from './PublicHeader';
import { RouteError } from './RouteError';
import type { AppServices } from './services';

/**
 * The route tree. Sign-in and the layouts load with the app; every other page is a lazy route, so a customer
 * signing in never downloads the console, and the console never downloads the chat. The root route hosts the auth
 * provider (it navigates, so it lives inside the router) and the error boundary; the layouts guard their areas by
 * role.
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
          children: [
            {
              index: true,
              lazy: async () => ({
                Component: (await import('@/pages/chat/CustomerChatPage')).CustomerChatPage,
              }),
            },
            {
              path: 'glass-box/:conversationId',
              lazy: async () => ({
                Component: (await import('@/pages/glass-box/GlassBoxPage')).GlassBoxPage,
              }),
            },
          ],
        },
        {
          path: 'console',
          element: <ConsoleLayout />,
          children: [
            {
              index: true,
              lazy: async () => ({
                Component: (await import('@/pages/console/ConsoleOverviewPage'))
                  .ConsoleOverviewPage,
              }),
            },
          ],
        },
        { path: '*', element: <NotFoundPage /> },
      ],
    },
  ];
}
