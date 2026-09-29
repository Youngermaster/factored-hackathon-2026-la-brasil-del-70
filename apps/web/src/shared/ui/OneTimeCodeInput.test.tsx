import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { OneTimeCodeInput } from './OneTimeCodeInput';

function Harness({ onComplete }: { readonly onComplete: (code: string) => void }) {
  const [code, setCode] = useState('');
  return (
    <>
      <label htmlFor="otp">Código</label>
      <OneTimeCodeInput id="otp" value={code} onValueChange={setCode} onComplete={onComplete} />
    </>
  );
}

describe('OneTimeCodeInput', () => {
  it('is one text field for one-time codes', () => {
    renderWithProviders(<Harness onComplete={vi.fn()} />);
    const input = screen.getByRole('textbox', { name: 'Código' });
    expect(input).toHaveAttribute('autocomplete', 'one-time-code');
    expect(input).toHaveAttribute('inputmode', 'numeric');
    expect(screen.getAllByRole('textbox')).toHaveLength(1);
  });

  it('keeps digits only while typing and completes at six', async () => {
    const onComplete = vi.fn();
    renderWithProviders(<Harness onComplete={onComplete} />);
    const input = screen.getByRole('textbox', { name: 'Código' });
    await userEvent.type(input, '12a3-45');
    expect(input).toHaveValue('12345');
    expect(onComplete).not.toHaveBeenCalled();
    await userEvent.type(input, '6');
    expect(onComplete).toHaveBeenCalledExactlyOnceWith('123456');
  });

  it('accepts a pasted code with separators', async () => {
    const onComplete = vi.fn();
    renderWithProviders(<Harness onComplete={onComplete} />);
    const input = screen.getByRole('textbox', { name: 'Código' });
    await userEvent.click(input);
    await userEvent.paste('482 915');
    expect(input).toHaveValue('482915');
    expect(onComplete).toHaveBeenCalledWith('482915');
  });

  it('ignores extra pasted digits', async () => {
    renderWithProviders(<Harness onComplete={vi.fn()} />);
    const input = screen.getByRole('textbox', { name: 'Código' });
    await userEvent.click(input);
    await userEvent.paste('12345678');
    expect(input).toHaveValue('123456');
  });

  it('deletes the last digit with backspace', async () => {
    renderWithProviders(<Harness onComplete={vi.fn()} />);
    const input = screen.getByRole('textbox', { name: 'Código' });
    await userEvent.type(input, '1234');
    await userEvent.keyboard('{Backspace}{Backspace}');
    expect(input).toHaveValue('12');
  });
});
