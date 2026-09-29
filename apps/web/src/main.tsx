import '@fontsource-variable/geist-mono';
import '@fontsource-variable/instrument-sans';
import '@fontsource-variable/unbounded';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from '@/app/App';
import '@/index.css';

const container = document.getElementById('root');
if (container === null) {
  throw new Error('The #root element is missing from index.html');
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
