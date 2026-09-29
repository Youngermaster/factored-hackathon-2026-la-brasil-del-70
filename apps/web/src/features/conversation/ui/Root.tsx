import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';

import { useStepUp } from '@/features/auth';
import { ApiError } from '@/shared/api';
import { useLocale, type Language } from '@/shared/i18n';

import {
  useConversationHistory,
  useCreateConversation,
  useSendTurn,
  type TurnView,
} from '../api/conversation';
import { ConversationContext, type LoadStatus } from '../model/context';
import { chatReducer, initialChatState } from '../model/pending';
import { replyKey, replyLanguage, type QuickReply } from '../model/replies';

const PARAM = 'conversation';

function loadStatusOf(
  conversationId: string | null,
  history: ReturnType<typeof useConversationHistory>,
): LoadStatus {
  if (conversationId === null) {
    return 'new';
  }
  if (history.isPending) {
    return 'loading';
  }
  if (history.isError) {
    return history.error instanceof ApiError && history.error.status === 404
      ? 'not_found'
      : 'error';
  }
  return 'ready';
}

function latestAnswered(turns: readonly TurnView[]): TurnView | undefined {
  return turns.findLast((turn) => turn.message !== null);
}

/**
 * The conversation's scope: the id (kept in `?conversation=`, so a reload or a re-authentication resumes it), the
 * history (server state), the customer's messages in flight, and the turn actions. Parts read it through
 * `useConversation()`; nothing is passed down as props.
 */
export function Root({ children }: { readonly children: ReactNode }) {
  const { i18n } = useTranslation();
  const { language: viewerLanguage } = useLocale();
  const [params, setParams] = useSearchParams();
  const conversationId = params.get(PARAM);
  const history = useConversationHistory(conversationId);
  const create = useCreateConversation();
  const { mutateAsync: sendTurn } = useSendTurn();
  const { requestStepUp } = useStepUp();
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const [draft, setDraft] = useState('');

  // Async chains (create, send, step up) read the latest id and language, not the ones of the render that started.
  const idRef = useRef(conversationId);
  const turns = useMemo(() => history.data?.turns ?? [], [history.data]);
  const latest = latestAnswered(turns);
  const language: Language | null = latest?.message?.language ?? null;
  const languageRef = useRef(replyLanguage(language, viewerLanguage));
  useEffect(() => {
    idRef.current = conversationId;
    languageRef.current = replyLanguage(language, viewerLanguage);
  }, [conversationId, language, viewerLanguage]);

  const phrase = useCallback(
    (reply: QuickReply) =>
      i18n.getFixedT(languageRef.current)(
        replyKey(reply),
        reply.kind === 'option' ? { number: reply.number } : {},
      ),
    [i18n],
  );

  const deliver = useCallback(
    async (firstTurnId: string, firstText: string): Promise<void> => {
      let turnId = firstTurnId;
      let text = firstText;
      // A write that needs a step-up continues with one more message once the code is verified.
      for (;;) {
        try {
          let id = idRef.current;
          if (id === null) {
            id = (await create.mutateAsync()).conversation_id;
            idRef.current = id;
            setParams({ [PARAM]: id }, { replace: true });
          }
          const response = await sendTurn({ conversationId: id, turnId, text });
          dispatch({ type: 'settled', turnId });
          if (!response.message.step_up_required) {
            return;
          }
          if (!(await requestStepUp())) {
            dispatch({
              type: 'notice',
              notice: { id: crypto.randomUUID(), code: 'step_up_cancelled', afterTurnId: turnId },
            });
            return;
          }
          turnId = crypto.randomUUID();
          text = phrase({ kind: 'stepped_up' });
          dispatch({ type: 'sent', turnId, text });
        } catch (error) {
          dispatch({ type: 'failed', turnId, error });
          return;
        }
      }
    },
    [create, phrase, requestStepUp, sendTurn, setParams],
  );

  const inFlight = state.pending.some((turn) => turn.status === 'sending');

  const send = useCallback(
    (raw: string) => {
      const text = raw.trim();
      if (text === '' || inFlight) {
        return;
      }
      const turnId = crypto.randomUUID();
      dispatch({ type: 'sent', turnId, text });
      void deliver(turnId, text);
    },
    [deliver, inFlight],
  );

  const reply = useCallback(
    (quick: QuickReply) => {
      send(phrase(quick));
      composerRef.current?.focus();
    },
    [phrase, send],
  );

  const retry = useCallback(
    (turnId: string) => {
      const turn = state.pending.find((item) => item.turnId === turnId);
      if (turn === undefined || inFlight) {
        return;
      }
      dispatch({ type: 'retrying', turnId });
      void deliver(turnId, turn.text);
    },
    [deliver, inFlight, state.pending],
  );

  const stepUpAgain = useCallback(() => {
    void requestStepUp().then((verified) => {
      if (verified) {
        send(phrase({ kind: 'stepped_up' }));
      }
    });
  }, [phrase, requestStepUp, send]);

  const startNew = useCallback(() => {
    idRef.current = null;
    dispatch({ type: 'reset' });
    setParams({}, { replace: false });
    composerRef.current?.focus();
  }, [setParams]);

  const { refetch } = history;
  const value = useMemo(
    () => ({
      conversationId,
      conversation: history.data?.conversation ?? null,
      turns,
      pending: state.pending,
      notices: state.notices,
      loadStatus: loadStatusOf(conversationId, history),
      loadError: history.error,
      reload: () => {
        void refetch();
      },
      inFlight,
      latestTurnId: latest?.turn_id ?? null,
      language,
      send,
      reply,
      retry,
      stepUpAgain,
      startNew,
      composerRef,
      draft,
      setDraft,
    }),
    [
      conversationId,
      history,
      refetch,
      turns,
      state,
      inFlight,
      latest,
      language,
      send,
      reply,
      retry,
      stepUpAgain,
      startNew,
      draft,
    ],
  );

  return <ConversationContext value={value}>{children}</ConversationContext>;
}
