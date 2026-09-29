import { render, type RenderOptions } from '@testing-library/react';
import { createElement, type ReactElement, type ReactNode } from 'react';

import { SharedProviders, type ProviderOptions } from './providers';

/** Renders with the shared providers (theme, locale, icons, tooltips, toasts). */
export function renderWithProviders(
  ui: ReactElement,
  { locale, theme, ...options }: ProviderOptions & Omit<RenderOptions, 'wrapper'> = {},
) {
  const providerProps: ProviderOptions = {
    ...(locale === undefined ? {} : { locale }),
    ...(theme === undefined ? {} : { theme }),
  };
  return render(ui, {
    wrapper: ({ children }: { readonly children: ReactNode }) =>
      createElement(SharedProviders, { ...providerProps, children }),
    ...options,
  });
}
