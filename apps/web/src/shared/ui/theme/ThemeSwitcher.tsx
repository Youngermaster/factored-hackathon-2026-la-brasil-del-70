import { useId } from 'react';
import { useTranslation } from 'react-i18next';

import type { ThemePreference } from '@/shared/lib/preferences';

import { Select } from '../Select';
import { useTheme } from './context';

/** Theme choice: follow the system, light, or dark. */
export function ThemeSwitcher({ className }: { readonly className?: string }) {
  const { t } = useTranslation();
  const { preference, setPreference } = useTheme();
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-2 block text-small font-medium text-fg">
        {t('preferences.theme')}
      </label>
      <Select
        id={id}
        value={preference}
        onChange={(event) => {
          setPreference(event.target.value as ThemePreference);
        }}
      >
        <option value="system">{t('preferences.themeSystem')}</option>
        <option value="light">{t('preferences.themeLight')}</option>
        <option value="dark">{t('preferences.themeDark')}</option>
      </Select>
    </div>
  );
}
