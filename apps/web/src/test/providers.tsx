import type { ReactNode } from 'react';

import { LocaleProvider, type AppLocale } from '@/shared/i18n';
import type { ThemePreference } from '@/shared/lib/preferences';
import { IconContext, ThemeProvider, ToastProvider, TooltipProvider } from '@/shared/ui';

export interface ProviderOptions {
  readonly locale?: AppLocale;
  readonly theme?: ThemePreference;
}

/** The shared providers every component expects: theme, locale (UTC in tests), icons, tooltips, and toasts. */
export function SharedProviders({
  children,
  locale = 'es-MX',
  theme = 'light',
}: ProviderOptions & { readonly children: ReactNode }) {
  return (
    <ThemeProvider initialPreference={theme}>
      <LocaleProvider locale={locale} timeZone="UTC">
        <IconContext value={{ size: 20, weight: 'regular' }}>
          <TooltipProvider delayDuration={0}>
            <ToastProvider>{children}</ToastProvider>
          </TooltipProvider>
        </IconContext>
      </LocaleProvider>
    </ThemeProvider>
  );
}
