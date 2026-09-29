import { useEffect, useState, type SyntheticEvent } from 'react';

import {
  ApiRequestError,
  changeAssistantName,
  createConversation,
  getAssistantProfile,
  getConversation,
  mockAssistantImage,
} from '@/features/assistant-profile';
import type { AssistantProfile } from '@/features/assistant-profile';

interface ChatState {
  conversationId: string;
  profile: AssistantProfile;
}

function routeConversationId(): string | null {
  const match = /^\/chat\/([A-Za-z0-9_-]{1,64})$/.exec(window.location.pathname);
  return match?.[1] ?? null;
}

function setChatRoute(conversationId: string): void {
  window.history.pushState({}, '', `/chat/${encodeURIComponent(conversationId)}`);
}

function loadError(error: unknown): string {
  if (error instanceof ApiRequestError && error.status === 401)
    return 'Sign in to open your assistant profile.';
  return 'The assistant profile could not be loaded. Try again.';
}

export function App() {
  const [chat, setChat] = useState<ChatState | null>(null);
  const [draftName, setDraftName] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function openCurrentChat(): Promise<void> {
      try {
        let conversationId = routeConversationId();
        if (conversationId === null) {
          const conversation = await createConversation();
          conversationId = conversation.conversation_id;
          setChatRoute(conversationId);
        } else {
          await getConversation(conversationId);
        }
        const profile = await getAssistantProfile(conversationId);
        if (active) {
          setChat({ conversationId, profile });
          setDraftName(profile.assistant_name);
          setError(null);
        }
      } catch (cause: unknown) {
        if (active) setError(loadError(cause));
      } finally {
        if (active) setLoading(false);
      }
    }

    void openCurrentChat();
    return () => {
      active = false;
    };
  }, []);

  async function saveName(event: SyntheticEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (chat === null) return;
    setBusy(true);
    setError(null);
    try {
      const profile = await changeAssistantName(chat.conversationId, draftName);
      setChat({ ...chat, profile });
      setDraftName(profile.assistant_name);
    } catch {
      setError('The name could not be saved. Check it and try again.');
    } finally {
      setBusy(false);
    }
  }

  async function changeImage(): Promise<void> {
    if (chat === null) return;
    setBusy(true);
    setError(null);
    try {
      const profile = await mockAssistantImage(chat.conversationId);
      setChat({ ...chat, profile });
    } catch {
      setError('The assistant image could not be changed. Try again.');
    } finally {
      setBusy(false);
    }
  }

  async function openNewChat(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const conversation = await createConversation();
      const profile = await getAssistantProfile(conversation.conversation_id);
      setChatRoute(conversation.conversation_id);
      setChat({ conversationId: conversation.conversation_id, profile });
      setDraftName(profile.assistant_name);
    } catch (cause: unknown) {
      setError(loadError(cause));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-3xl items-center p-6">
        Loading assistant profile…
      </main>
    );
  }

  if (chat === null) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-3xl flex-col justify-center gap-4 p-6">
        <h1 className="text-2xl font-semibold tracking-tight">Bank Agent</h1>
        <p role="alert">{error ?? 'The assistant profile is unavailable.'}</p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col gap-8 p-6">
      <header aria-label="Chat header" className="flex items-center gap-4 rounded-xl border p-4">
        <img
          alt={`${chat.profile.assistant_name} avatar`}
          className="size-16 rounded-full object-cover"
          height={64}
          src={chat.profile.avatar_url}
          width={64}
        />
        <div className="min-w-0 flex-1">
          <p className="text-sm text-slate-500">Your assistant</p>
          <h1 className="truncate text-2xl font-semibold tracking-tight">
            {chat.profile.assistant_name}
          </h1>
        </div>
        <button
          className="rounded-md border px-3 py-2"
          disabled={busy}
          onClick={() => void changeImage()}
          type="button"
        >
          Change image
        </button>
      </header>

      <section aria-label="Assistant preferences" className="flex flex-col gap-4">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            void saveName(event);
          }}
        >
          <div className="flex min-w-56 flex-1 flex-col gap-1">
            <label className="text-sm font-medium" htmlFor="assistant-name">
              Assistant name
            </label>
            <input
              autoComplete="off"
              className="rounded-md border px-3 py-2"
              id="assistant-name"
              maxLength={40}
              onChange={(event) => {
                setDraftName(event.target.value);
              }}
              required
              value={draftName}
            />
          </div>
          <button
            className="rounded-md bg-slate-900 px-4 py-2 text-white"
            disabled={busy}
            type="submit"
          >
            Save name
          </button>
          <button
            className="rounded-md border px-4 py-2"
            disabled={busy}
            onClick={() => void openNewChat()}
            type="button"
          >
            New chat
          </button>
        </form>
        <p aria-live="polite" className="text-sm text-red-700" role={error ? 'alert' : undefined}>
          {error ?? ''}
        </p>
        <p className="text-xs text-slate-500">Conversation: {chat.conversationId}</p>
      </section>
    </main>
  );
}
