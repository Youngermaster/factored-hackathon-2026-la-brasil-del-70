import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '@/test/render';

import * as Field from './Field';
import { Input, Textarea } from './Input';
import { Select } from './Select';

function DocumentField({ invalid }: { readonly invalid: boolean }) {
  return (
    <Field.Root invalid={invalid} required hasHint>
      <Field.Label>Número de documento</Field.Label>
      <Field.Control>
        <Input />
      </Field.Control>
      <Field.Hint>De 4 a 20 caracteres.</Field.Hint>
      <Field.Error>Revisa el número.</Field.Error>
    </Field.Root>
  );
}

describe('Field', () => {
  it('labels the control and describes it with the hint', () => {
    renderWithProviders(<DocumentField invalid={false} />);
    const input = screen.getByRole('textbox', { name: 'Número de documento' });
    expect(input).toHaveAccessibleDescription('De 4 a 20 caracteres.');
    expect(input).not.toHaveAttribute('aria-invalid');
    expect(input).toHaveAttribute('aria-required', 'true');
    expect(screen.queryByText('Revisa el número.')).toBeNull();
  });

  it('marks the control invalid and adds the error to its description', () => {
    renderWithProviders(<DocumentField invalid />);
    const input = screen.getByRole('textbox', { name: 'Número de documento' });
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAccessibleDescription('De 4 a 20 caracteres. Revisa el número.');
  });

  it('refuses parts outside a root', () => {
    expect(() => renderWithProviders(<Field.Label>Sin raíz</Field.Label>)).toThrow(/Field.Root/);
  });
});

describe('Textarea and Select', () => {
  it('accept typing and choosing', async () => {
    renderWithProviders(
      <>
        <label htmlFor="nota">Nota</label>
        <Textarea id="nota" />
        <label htmlFor="pais">País</label>
        <Select id="pais" defaultValue="MX">
          <option value="MX">México</option>
          <option value="CO">Colombia</option>
        </Select>
      </>,
    );
    await userEvent.type(screen.getByRole('textbox', { name: 'Nota' }), 'Hola');
    expect(screen.getByRole('textbox', { name: 'Nota' })).toHaveValue('Hola');
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'País' }), 'CO');
    expect(screen.getByRole('combobox', { name: 'País' })).toHaveValue('CO');
  });
});
