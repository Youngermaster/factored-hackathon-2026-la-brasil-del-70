import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { axe } from '@/test/axe';
import { renderWithProviders } from '@/test/render';

import { AsOfNote } from './AsOfNote';
import { Badge } from './Badge';
import * as Card from './Card';
import { JsonView } from './JsonView';
import * as KeyValueList from './KeyValueList';
import { Inline, Stack } from './layout';
import { Skeleton, SkeletonGroup } from './Skeleton';
import { EmptyState, ErrorState } from './states';
import { StatusPill, type Status } from './StatusPill';
import * as Timeline from './Timeline';

describe('StatusPill', () => {
  it.each([
    ['verified', 'Verificado', 'bg-decision'],
    ['pending', 'Pendiente', 'bg-surface-sunken'],
    ['failed', 'Falló', 'bg-risk-subtle'],
    ['escalated', 'Con una persona', 'bg-risk-subtle'],
    ['review_required', 'Requiere revisión', 'bg-surface'],
  ] as const)('%s reads "%s"', (status: Status, label, fill) => {
    renderWithProviders(<StatusPill status={status} />);
    const pill = screen.getByText(label).closest('[data-status]');
    expect(pill?.className).toContain(fill);
  });

  it('never gives a review the yellow verified fill', () => {
    renderWithProviders(<StatusPill status="review_required" />);
    expect(screen.getByText('Requiere revisión').closest('[data-status]')?.className).not.toContain(
      'bg-decision',
    );
  });

  it('translates with the locale', () => {
    renderWithProviders(<StatusPill status="verified" />, { locale: 'pt-BR' });
    expect(screen.getByText('Verificado')).toBeInTheDocument();
  });
});

describe('AsOfNote', () => {
  it('states the as-of instant in a time element', () => {
    renderWithProviders(<AsOfNote at="2026-09-27T15:04:00Z" />, { locale: 'en-US' });
    const time = screen.getByText(/Data as of Sep 27, 2026/);
    expect(time.tagName).toBe('TIME');
    expect(time).toHaveAttribute('datetime', '2026-09-27T15:04:00Z');
  });
});

describe('Card and KeyValueList', () => {
  it('render a titled section with label and value pairs', async () => {
    const { container } = renderWithProviders(
      <Card.Root aria-labelledby="saldo">
        <Card.Header
          title={<span id="saldo">Cuenta de ahorro</span>}
          description="Terminada en 4821"
        />
        <Card.Body>
          <KeyValueList.Root columns={2}>
            <KeyValueList.Item label="Saldo" numeric>
              $12,450.10
            </KeyValueList.Item>
            <KeyValueList.Item label="Estado">Activa</KeyValueList.Item>
          </KeyValueList.Root>
        </Card.Body>
        <Card.Footer>
          <Badge tone="understanding">Modelo</Badge>
        </Card.Footer>
      </Card.Root>,
    );
    expect(screen.getByRole('region', { name: 'Cuenta de ahorro' })).toBeInTheDocument();
    expect(screen.getAllByRole('term').map((term) => term.textContent)).toEqual([
      'Saldo',
      'Estado',
    ]);
    expect(screen.getByText('$12,450.10').className).toContain('tabular-nums');
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('states', () => {
  it('EmptyState explains and offers an action', () => {
    renderWithProviders(
      <EmptyState
        title="Sin traspasos"
        description="Aparecerán cuando el asistente escale un caso."
        action={<button type="button">Actualizar</button>}
      />,
    );
    expect(screen.getByText('Sin traspasos')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Actualizar' })).toBeInTheDocument();
  });

  it('ErrorState is an alert with the request id for support', () => {
    renderWithProviders(<ErrorState title="No se pudo cargar" requestId="req-7f3a" />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('No se pudo cargar');
    expect(alert).toHaveTextContent('Referencia para soporte: req-7f3a');
  });

  it('SkeletonGroup announces loading once and hides the blocks', () => {
    const { container } = renderWithProviders(
      <SkeletonGroup>
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-4 w-24" />
      </SkeletonGroup>,
    );
    expect(screen.getByRole('status')).toHaveTextContent('Cargando');
    expect(container.querySelectorAll('[aria-hidden="true"]')).toHaveLength(2);
  });
});

describe('layout', () => {
  it('Stack and Inline render the requested element and gap', () => {
    renderWithProviders(
      <Stack as="ul" gap={6} aria-label="lista">
        <li>
          <Inline as="nav" gap={2} aria-label="acciones">
            <span>a</span>
          </Inline>
        </li>
      </Stack>,
    );
    expect(screen.getByRole('list', { name: 'lista' }).className).toContain('gap-6');
    expect(screen.getByRole('navigation', { name: 'acciones' }).className).toContain('gap-2');
  });
});

describe('Timeline', () => {
  it('is an ordered list whose steps carry their tone and meta', () => {
    renderWithProviders(
      <Timeline.Root aria-label="Traza">
        <Timeline.Item tone="understanding" title="Intención: aclaración" meta="412 ms" />
        <Timeline.Item tone="decision" title="Regla DSP-MX-1 cumplida">
          Ventana de 90 días
        </Timeline.Item>
        <Timeline.Item tone="risk" title="Escalado a una persona" />
      </Timeline.Root>,
    );
    const items = screen.getAllByRole('listitem');
    expect(items.map((item) => item.dataset['tone'])).toEqual([
      'understanding',
      'decision',
      'risk',
    ]);
    expect(screen.getByText('412 ms')).toBeInTheDocument();
  });
});

describe('JsonView', () => {
  it('shows markup inside values as text, never as HTML', () => {
    renderWithProviders(
      <JsonView
        label="Registro"
        value={{ note: '<img src=x onerror=alert(1)>', amount: '12.50' }}
      />,
    );
    const region = screen.getByRole('region', { name: 'Registro' });
    expect(region).toHaveTextContent('"note": "<img src=x onerror=alert(1)>"');
    expect(region.querySelector('img')).toBeNull();
    expect(region).toHaveAttribute('tabindex', '0');
  });
});
