import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { currentPath, renderApp } from '@/test/app';
import { apiGet, apiPost, sessionView } from '@/test/msw/api';
import { startAuthServer } from '@/test/msw/auth';
import { startConversationServer } from '@/test/msw/conversation';
import { server } from '@/test/msw/server';

import type { AssistantProfile } from './api/profile';

function startProfileServer() {
  let profile: AssistantProfile = {
    assistant_name: 'Assistant',
    avatar_key: 'avatar_1',
    avatar_url: '/v1/assistant-profile/avatars/avatar_1.png',
    updated_at: null,
  };
  const reads: string[] = [];
  server.use(
    apiGet('/v1/conversations/:id/assistant-profile', ({ params }) => {
      reads.push(String(params['id']));
      return HttpResponse.json(profile);
    }),
    apiPost('/v1/conversations/:id/assistant-profile/name', async ({ request }) => {
      const body = (await request.json()) as { name: string };
      if (body.name === 'Taken') return HttpResponse.json({}, { status: 422 });
      profile = { ...profile, assistant_name: body.name, updated_at: '2026-09-29T12:00:00Z' };
      return HttpResponse.json(profile);
    }),
    apiPost('/v1/conversations/:id/assistant-profile/mock-image', () => {
      const avatar_key = profile.avatar_key === 'avatar_1' ? 'avatar_2' : 'avatar_1';
      profile = {
        ...profile,
        avatar_key,
        avatar_url: `/v1/assistant-profile/avatars/${avatar_key}.png`,
        updated_at: '2026-09-29T12:00:00Z',
      };
      return HttpResponse.json(profile);
    }),
  );
  return { reads };
}

async function openProfile() {
  await userEvent.click(await screen.findByRole('button', { name: 'Assistant profile' }));
  return screen.findByRole('dialog', { name: 'Assistant profile' });
}

describe('assistant profile in the routed customer chat', () => {
  it('loads and edits the saved name and PNG, then restores them in a new chat and after refresh', async () => {
    startAuthServer({ session: sessionView({ language_preference: 'en' }) });
    startConversationServer();
    const profile = startProfileServer();
    const first = renderApp({ locale: 'en-US' });

    await waitFor(() => {
      expect(profile.reads).toContain('conv-new-1');
    });

    const dialog = await openProfile();
    expect(within(dialog).getByRole('img', { name: 'Assistant avatar' })).toHaveAttribute(
      'src',
      '/v1/assistant-profile/avatars/avatar_1.png',
    );
    const name = within(dialog).getByRole('textbox', { name: 'Assistant name' });
    await userEvent.clear(name);
    await userEvent.type(name, 'Camila');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save name' }));
    await waitFor(() =>
      expect(within(dialog).getByRole('img', { name: 'Camila avatar' })).toBeInTheDocument(),
    );
    await userEvent.click(within(dialog).getByRole('button', { name: 'Change image' }));
    await waitFor(() =>
      expect(within(dialog).getByRole('img', { name: 'Camila avatar' })).toHaveAttribute(
        'src',
        '/v1/assistant-profile/avatars/avatar_2.png',
      ),
    );

    await userEvent.click(within(dialog).getByRole('button', { name: 'Close' }));
    await userEvent.click(screen.getByRole('button', { name: 'New conversation' }));
    await waitFor(() => {
      expect(profile.reads).toContain('conv-new-2');
    });
    expect(screen.getByRole('button', { name: 'Assistant profile' })).toHaveTextContent('Camila');
    const path = currentPath(first.router);
    first.unmount();

    renderApp({ path, locale: 'en-US' });
    await waitFor(() => {
      expect(profile.reads.filter((id) => id === 'conv-new-2')).toHaveLength(2);
    });
    expect(screen.getByRole('button', { name: 'Assistant profile' })).toHaveTextContent('Camila');
  });

  it('keeps the saved header when the name update is rejected', async () => {
    startAuthServer({ session: sessionView({ language_preference: 'en' }) });
    startConversationServer();
    startProfileServer();
    renderApp({ locale: 'en-US' });
    const dialog = await openProfile();
    await waitFor(() =>
      expect(within(dialog).getByRole('button', { name: 'Save name' })).toBeEnabled(),
    );
    const name = within(dialog).getByRole('textbox', { name: 'Assistant name' });
    await userEvent.clear(name);
    await userEvent.type(name, 'Taken');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save name' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'The name could not be saved.',
    );
    expect(within(dialog).getByRole('img', { name: 'Assistant avatar' })).toBeInTheDocument();
  });
});
