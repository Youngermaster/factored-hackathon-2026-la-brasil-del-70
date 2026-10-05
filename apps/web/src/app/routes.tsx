import { Outlet, type RouteObject } from 'react-router';

import { AuthProvider } from '@/features/auth';
import { LoginPage } from '@/pages/login/LoginPage';
import { NotFoundPage } from '@/pages/not-found/NotFoundPage';
import { isDemoMode } from '@/shared/config';

import { ConsoleLayout } from './layouts/ConsoleLayout';
import { CustomerLayout } from './layouts/CustomerLayout';
import { PublicHeader } from './PublicHeader';
import { PublicLayout } from './PublicLayout';
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
          element: <PublicLayout />,
          children: [
            {
              path: 'about',
              lazy: async () => ({
                Component: (await import('@/pages/about/AboutPage')).AboutPage,
              }),
            },
            // The demo guide exists only in demo mode; otherwise /demo is not found.
            ...(isDemoMode()
              ? [
                  {
                    path: 'demo',
                    lazy: async () => ({
                      Component: (await import('@/pages/demo/DemoGuidePage')).DemoGuidePage,
                    }),
                  },
                ]
              : []),
          ],
        },
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
            {
              path: 'inbox',
              lazy: async () => ({
                Component: (await import('@/pages/inbox/AgentInboxPage')).AgentInboxPage,
              }),
            },
            {
              path: 'inbox/:handoffId',
              lazy: async () => ({
                Component: (await import('@/pages/inbox/HandoffDetailPage')).HandoffDetailPage,
              }),
            },
            {
              path: 'credit-applications',
              lazy: async () => ({
                Component: (await import('@/pages/credit-applications/CreditApplicationsPage'))
                  .CreditApplicationsPage,
              }),
            },
            {
              path: 'credit-applications/:applicationId',
              lazy: async () => ({
                Component: (await import('@/pages/credit-applications/CreditApplicationPage'))
                  .CreditApplicationPage,
              }),
            },
            {
              path: 'supervision',
              lazy: async () => ({
                Component: (await import('@/pages/supervision/SupervisionPage')).SupervisionPage,
              }),
            },
            {
              path: 'dashboard',
              lazy: async () => ({
                Component: (await import('@/pages/dashboard/AdminDashboardPage'))
                  .AdminDashboardPage,
              }),
            },
            {
              path: 'evaluation',
              lazy: async () => ({
                Component: (await import('@/pages/evaluation/EvaluationPage')).EvaluationPage,
              }),
            },
            {
              path: 'traces',
              lazy: async () => ({
                Component: (await import('@/pages/traces/TraceLookupPage')).TraceLookupPage,
              }),
            },
            {
              path: 'traces/:conversationId',
              lazy: async () => ({
                Component: (await import('@/pages/traces/TraceLookupPage')).TraceLookupPage,
              }),
            },
          ],
        },
        { path: '*', element: <NotFoundPage /> },
      ],
    },
  ];
}
