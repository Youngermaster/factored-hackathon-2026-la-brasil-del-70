import { useTranslation } from 'react-i18next';

import { LocaleSwitcher } from '@/shared/i18n';
import { IconButton, SettingsIcon, Sheet, ThemeSwitcher, Tooltip } from '@/shared/ui';

/** Theme and language in a side sheet, reachable from every layout. */
export function Preferences() {
  const { t } = useTranslation();
  return (
    <Sheet.Root>
      <Tooltip content={t('preferences.title')}>
        <Sheet.Trigger asChild>
          <IconButton label={t('preferences.title')} icon={<SettingsIcon />} />
        </Sheet.Trigger>
      </Tooltip>
      <Sheet.Content aria-describedby={undefined}>
        <Sheet.Title>{t('preferences.title')}</Sheet.Title>
        <LocaleSwitcher />
        <ThemeSwitcher />
      </Sheet.Content>
    </Sheet.Root>
  );
}
