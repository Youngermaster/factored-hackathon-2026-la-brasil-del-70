import { useId } from 'react';
import { useTranslation } from 'react-i18next';

import { Select } from '@/shared/ui/Select';

import { useLocale } from './context';
import { isAppLocale, LOCALE_NAMES, SUPPORTED_LOCALES } from './locales';

/** Language and region: the language picks the copy, the region the money and date formats. */
export function LocaleSwitcher({ className }: { readonly className?: string }) {
  const { t } = useTranslation();
  const { locale, setLocale } = useLocale();
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-2 block text-small font-medium text-fg">
        {t('preferences.locale')}
      </label>
      <Select
        id={id}
        value={locale}
        onChange={(event) => {
          if (isAppLocale(event.target.value)) {
            setLocale(event.target.value);
          }
        }}
      >
        {SUPPORTED_LOCALES.map((option) => (
          <option key={option} value={option} lang={option}>
            {LOCALE_NAMES[option]}
          </option>
        ))}
      </Select>
    </div>
  );
}
