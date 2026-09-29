import { QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import { ApiProvider } from '@/shared/api';
import { LocaleProvider, type AppLocale } from '@/shared/i18n';
import type { ThemePreference } from '@/shared/lib/preferences';
import { IconContext, ThemeProvider, ToastProvider, TooltipProvider } from '@/shared/ui';

import type { AppServices } from './services';

const iconDefaults = { size: 20, weight: 'regular' } as const;

/**
 * The composition root's providers: theme, locale and formatters, icons, tooltips, toasts, the query client, and
 * the API client. Features consume them through hooks (useTheme, useLocale, useApi, ...), never through props.
 */
export function AppProviders({
  services,
  locale,
  theme,
  timeZone,
  children,
}: {
  readonly services: AppServices;
  readonly locale?: AppLocale;
  readonly theme?: ThemePreference;
  readonly timeZone?: string;
  readonly children: ReactNode;
}) {
  return (
    <ThemeProvider {...(theme === undefined ? {} : { initialPreference: theme })}>
      <LocaleProvider
        {...(locale === undefined ? {} : { locale })}
        {...(timeZone === undefined ? {} : { timeZone })}
      >
        <IconContext value={iconDefaults}>
          <TooltipProvider delayDuration={300}>
            <ToastProvider>
              <QueryClientProvider client={services.queryClient}>
                <ApiProvider value={services.api}>{children}</ApiProvider>
              </QueryClientProvider>
            </ToastProvider>
          </TooltipProvider>
        </IconContext>
      </LocaleProvider>
    </ThemeProvider>
  );
}
