import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { App } from '@/app/App';
import type { AssistantProfile } from '@/features/assistant-profile';
import { server } from '@/test/msw/server';

const baseProfile: AssistantProfile = {
  assistant_name: 'Assistant',
  avatar_key: 'avatar_1',
  avatar_url: '/api/v1/assistant-profile/avatars/avatar_1.png',
  updated_at: null,
};

function installProfileApi(): { getActiveProfile: () => AssistantProfile } {
  let profile = baseProfile;
  let nextConversation = 1;
  server.use(
    http.get('*/api/v1/auth/csrf', () => HttpResponse.json({ csrf_token: 'csrf-test-token' })),
    http.post('*/api/v1/conversations', () => {
      nextConversation += 1;
      return HttpResponse.json(
        { conversation_id: `conv-${String(nextConversation)}` },
        { status: 201 },
      );
    }),
    http.get('*/api/v1/conversations/:conversationId', () =>
      HttpResponse.json({ conversation: {}, turns: [] }),
    ),
    http.get('*/api/v1/conversations/:conversationId/assistant-profile', () =>
      HttpResponse.json(profile),
    ),
    http.post(
      '*/api/v1/conversations/:conversationId/assistant-profile/name',
      async ({ request }) => {
        const body: unknown = await request.json();
        if (
          typeof body !== 'object' ||
          body === null ||
          !('name' in body) ||
          typeof body.name !== 'string'
        ) {
          return HttpResponse.json({ title: 'Invalid name' }, { status: 422 });
        }
        if (body.name === 'Taken')
          return HttpResponse.json({ title: 'Invalid name' }, { status: 422 });
        profile = { ...profile, assistant_name: body.name, updated_at: '2026-09-29T12:00:00Z' };
        return HttpResponse.json(profile);
      },
    ),
    http.post('*/api/v1/conversations/:conversationId/assistant-profile/mock-image', () => {
      const avatarKey = profile.avatar_key === 'avatar_1' ? 'avatar_2' : 'avatar_1';
      profile = {
        ...profile,
        avatar_key: avatarKey,
        avatar_url: `/api/v1/assistant-profile/avatars/${avatarKey}.png`,
        updated_at: '2026-09-29T12:00:00Z',
      };
      return HttpResponse.json(profile);
    }),
  );
  return { getActiveProfile: () => profile };
}

describe('assistant profile chat header', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/chat/conv-1');
  });

  it('shows the saved name and PNG and updates them after successful changes', async () => {
    installProfileApi();
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByRole('heading', { level: 1, name: 'Assistant' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Assistant avatar' })).toHaveAttribute(
      'src',
      '/api/v1/assistant-profile/avatars/avatar_1.png',
    );

    const name = screen.getByRole('textbox', { name: 'Assistant name' });
    await user.clear(name);
    await user.type(name, 'Camila');
    await user.click(screen.getByRole('button', { name: 'Save name' }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Camila' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Change image' }));
    await waitFor(() =>
      expect(screen.getByRole('img', { name: 'Camila avatar' })).toHaveAttribute(
        'src',
        '/api/v1/assistant-profile/avatars/avatar_2.png',
      ),
    );
  });

  it('keeps the saved header when the server rejects a name', async () => {
    installProfileApi();
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole('heading', { level: 1, name: 'Assistant' });

    const name = screen.getByRole('textbox', { name: 'Assistant name' });
    await user.clear(name);
    await user.type(name, 'Taken');
    await user.click(screen.getByRole('button', { name: 'Save name' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('The name could not be saved.');
    expect(screen.getByRole('heading', { level: 1, name: 'Assistant' })).toBeInTheDocument();
  });

  it('restores saved preferences on refresh and reuses them in another chat', async () => {
    const api = installProfileApi();
    const user = userEvent.setup();
    const first = render(<App />);
    await screen.findByRole('heading', { level: 1, name: 'Assistant' });

    const name = screen.getByRole('textbox', { name: 'Assistant name' });
    await user.clear(name);
    await user.type(name, 'Rafa');
    await user.click(screen.getByRole('button', { name: 'Save name' }));
    await screen.findByRole('heading', { level: 1, name: 'Rafa' });
    first.unmount();

    render(<App />);
    expect(await screen.findByRole('heading', { level: 1, name: 'Rafa' })).toBeInTheDocument();
    expect(api.getActiveProfile().assistant_name).toBe('Rafa');

    await user.click(screen.getByRole('button', { name: 'New chat' }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Rafa' })).toBeInTheDocument();
    expect(screen.getByText('Conversation: conv-2')).toBeInTheDocument();
    expect(window.location.pathname).toBe('/chat/conv-2');
  });

  it('shows the sign-in state for an unauthenticated session', async () => {
    server.use(
      http.get('*/api/v1/conversations/:conversationId', () =>
        HttpResponse.json({ title: 'Unauthenticated' }, { status: 401 }),
      ),
    );
    render(<App />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Sign in to open your assistant profile.',
    );
  });
});
