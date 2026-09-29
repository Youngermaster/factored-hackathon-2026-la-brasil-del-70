import { useState } from 'react';
import { createBrowserRouter } from 'react-router';
// The DOM RouterProvider wires ReactDOM.flushSync, which the session-loss redirect relies on.
import { RouterProvider } from 'react-router/dom';

import { AppProviders } from './AppProviders';
import { createRoutes } from './routes';
import { createAppServices } from './services';

/** The composition root: services are created once, then the providers and the router. */
export function App() {
  const [services] = useState(createAppServices);
  const [router] = useState(() => createBrowserRouter(createRoutes(services)));
  return (
    <AppProviders services={services}>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
