import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod/mini';

import { Button, Field, Input } from '@/shared/ui';

import type { LoginIdentification } from '../api/session';

// The same patterns as the API's DocumentLogin schema (contracts/openapi.json). zod/mini keeps the bundle small.
const schema = z.object({
  documentNumber: z.string().check(z.trim(), z.regex(/^[A-Za-z0-9-]{4,20}$/)),
  phoneLast4: z.string().check(z.trim(), z.regex(/^[0-9]{4}$/)),
});

type Values = z.infer<typeof schema>;

/**
 * Identification by document number and the last four phone digits. It only opens a challenge: the one-time code
 * is what proves identity.
 */
export function DocumentForm({
  onSubmit,
  pending,
}: {
  readonly onSubmit: (identification: LoginIdentification) => void;
  readonly pending: boolean;
}) {
  const { t } = useTranslation();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { documentNumber: '', phoneLast4: '' },
  });

  return (
    <form
      noValidate
      className="flex flex-col gap-5"
      onSubmit={(event) => {
        void handleSubmit((values) => {
          onSubmit({
            kind: 'document',
            document_number: values.documentNumber,
            phone_last4: values.phoneLast4,
          });
        })(event);
      }}
    >
      <Field.Root invalid={errors.documentNumber !== undefined} required hasHint>
        <Field.Label>{t('auth.documentNumber')}</Field.Label>
        <Field.Control>
          <Input autoComplete="off" spellCheck={false} {...register('documentNumber')} />
        </Field.Control>
        <Field.Hint>{t('auth.documentNumberHint')}</Field.Hint>
        <Field.Error>{t('auth.documentNumberInvalid')}</Field.Error>
      </Field.Root>
      <Field.Root invalid={errors.phoneLast4 !== undefined} required hasHint>
        <Field.Label>{t('auth.phoneLast4')}</Field.Label>
        <Field.Control>
          <Input
            inputMode="numeric"
            autoComplete="off"
            maxLength={4}
            className="max-w-32 font-mono tabular-nums"
            {...register('phoneLast4')}
          />
        </Field.Control>
        <Field.Hint>{t('auth.phoneLast4Hint')}</Field.Hint>
        <Field.Error>{t('auth.phoneLast4Invalid')}</Field.Error>
      </Field.Root>
      <Button type="submit" size="lg" pending={pending} className="self-start">
        {t('auth.sendCode')}
      </Button>
    </form>
  );
}
