import type { Language } from '@/shared/i18n';

/**
 * Quick replies: buttons that send text the engine's deterministic parsers read (yes or no, an ordinal choice, the
 * request for a person). The customer sees the sent words as their own message. The phrases live in the locale
 * files under `chat.replies`; the backend scenario tests use the same wording.
 */
export type QuickReply =
  | { readonly kind: 'confirm' }
  | { readonly kind: 'cancel' }
  | { readonly kind: 'option'; readonly number: number; readonly optionId: string }
  | { readonly kind: 'human' }
  | { readonly kind: 'review' }
  | { readonly kind: 'stepped_up' };

export type ReplyKey =
  | 'chat.replies.confirm'
  | 'chat.replies.cancel'
  | 'chat.replies.option'
  | 'chat.replies.human'
  | 'chat.replies.review'
  | 'chat.replies.steppedUp';

const KEYS: Record<QuickReply['kind'], ReplyKey> = {
  confirm: 'chat.replies.confirm',
  cancel: 'chat.replies.cancel',
  option: 'chat.replies.option',
  human: 'chat.replies.human',
  review: 'chat.replies.review',
  stepped_up: 'chat.replies.steppedUp',
};

export function replyKey(reply: QuickReply): ReplyKey {
  return KEYS[reply.kind];
}

/** The language quick replies are sent in: the conversation's latest language, else the viewer's. */
export function replyLanguage(conversation: Language | null, viewer: Language): Language {
  return conversation ?? viewer;
}
