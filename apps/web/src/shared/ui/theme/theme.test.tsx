import { act, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { LocaleSwitcher } from '@/shared/i18n';
import { PREFERENCES_KEY, readPreferences } from '@/shared/lib/preferences';
import { renderWithProviders } from '@/test/render';

import themeInit from '../../../../public/theme-init.js?raw';
import { ThemeSwitcher } from './ThemeSwitcher';

function mockSystemTheme(dark: boolean) {
  const listeners = new Set<() => void>();
  const query = {
    matches: dark,
    addEventListener: (_: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_: string, listener: () => void) => listeners.delete(listener),
  };
  vi.stubGlobal('matchMedia', () => query);
  return {
    change(next: boolean) {
      query.matches = next;
      listeners.forEach((listener) => {
        listener();
      });
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('ThemeProvider and ThemeSwitcher', () => {
  it('applies the chosen theme to <html> and remembers it', async () => {
    renderWithProviders(<ThemeSwitcher />, { theme: 'light' });
    expect(document.documentElement).toHaveAttribute('data-theme', 'light');
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Tema' }), 'dark');
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
    expect(readPreferences().theme).toBe('dark');
  });

  it('follows the system while the preference is system', () => {
    const system = mockSystemTheme(false);
    renderWithProviders(<ThemeSwitcher />, { theme: 'system' });
    expect(document.documentElement).toHaveAttribute('data-theme', 'light');
    act(() => {
      system.change(true);
    });
    expect(screen.getByRole('combobox', { name: 'Tema' })).toHaveValue('system');
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
  });
});

describe('LocaleSwitcher', () => {
  it('switches the copy and the formats, and updates <html lang>', async () => {
    renderWithProviders(<LocaleSwitcher />, { locale: 'es-CO' });
    const select = screen.getByRole('combobox', { name: 'Idioma y región' });
    await userEvent.selectOptions(select, 'pt-BR');
    expect(screen.getByRole('combobox', { name: 'Idioma e região' })).toHaveValue('pt-BR');
    expect(document.documentElement.lang).toBe('pt');
    expect(readPreferences().locale).toBe('pt-BR');
  });
});

describe('public/theme-init.js', () => {
  const run = () => {
    // The script is plain browser JavaScript served before the bundle; evaluate it as the browser would.
    window.eval(themeInit);
  };

  it('applies a stored explicit theme before the app starts', () => {
    window.localStorage.setItem(PREFERENCES_KEY, JSON.stringify({ theme: 'dark' }));
    run();
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
  });

  it('resolves the system theme when nothing valid is stored', () => {
    mockSystemTheme(true);
    window.localStorage.setItem(PREFERENCES_KEY, '{broken');
    run();
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
  });

  it('falls back to light without matchMedia', () => {
    vi.stubGlobal('matchMedia', undefined);
    run();
    expect(document.documentElement).toHaveAttribute('data-theme', 'light');
  });
});
