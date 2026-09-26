import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { App } from '@/app/App';

describe('App shell', () => {
  it('renders a main landmark with the product name as its heading', () => {
    render(<App />);

    const main = screen.getByRole('main');
    expect(main).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Bank Agent' })).toBeInTheDocument();
  });
});
