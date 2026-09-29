import { useTranslation } from 'react-i18next';

/** A masked product number: only the last four characters, ever, with the digits in the mono face. */
export function Masked({ last4 }: { readonly last4: string }) {
  const { t } = useTranslation();
  return (
    <span className="whitespace-nowrap">
      {t('parts.maskedPrefix')} <span className="font-mono tabular-nums">{last4}</span>
    </span>
  );
}
