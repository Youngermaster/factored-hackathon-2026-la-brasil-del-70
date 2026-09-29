import { useState, type SyntheticEvent } from 'react';
import { useTranslation } from 'react-i18next';

import { useConversation } from '@/features/conversation';
import { Button, Input, Sheet } from '@/shared/ui';

import {
  useAssistantProfile,
  useChangeAssistantImage,
  useChangeAssistantName,
} from '../api/profile';

const DEFAULT_AVATAR = '/v1/assistant-profile/avatars/avatar_1.png';

/** The customer profile in the existing chat header, with its edit controls in a sheet. */
export function AssistantProfileControl() {
  const { t } = useTranslation();
  const { conversationId } = useConversation();
  const profile = useAssistantProfile(conversationId);
  const changeName = useChangeAssistantName();
  const changeImage = useChangeAssistantImage();
  const [draft, setDraft] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const name = profile.data?.assistant_name ?? t('chat.assistant');
  const avatar = profile.data?.avatar_url ?? DEFAULT_AVATAR;
  const draftName = draft ?? name;

  async function saveName(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    if (conversationId === null) return;
    setActionError(null);
    try {
      await changeName.mutateAsync({ conversationId, name: draftName });
      setDraft(null);
    } catch {
      setActionError(t('chat.profile.saveError'));
    }
  }

  async function saveImage() {
    if (conversationId === null) return;
    setActionError(null);
    try {
      await changeImage.mutateAsync(conversationId);
    } catch {
      setActionError(t('chat.profile.imageError'));
    }
  }

  const busy = changeName.isPending || changeImage.isPending;
  return (
    <Sheet.Root
      onOpenChange={(open) => {
        if (!open) {
          setDraft(null);
          setActionError(null);
        }
      }}
    >
      <Sheet.Trigger asChild>
        <Button variant="ghost" size="sm" aria-label={t('chat.profile.open')}>
          <img
            src={avatar}
            alt=""
            width={28}
            height={28}
            className="size-7 rounded-full object-cover"
          />
          <span className="max-w-28 truncate">{name}</span>
        </Button>
      </Sheet.Trigger>
      <Sheet.Content aria-describedby={undefined}>
        <Sheet.Title>{t('chat.profile.title')}</Sheet.Title>
        <div className="flex items-center gap-4">
          <img
            src={avatar}
            alt={t('chat.profile.avatarAlt', { name })}
            width={64}
            height={64}
            className="size-16 rounded-full object-cover"
          />
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void saveImage()}
            disabled={conversationId === null || busy}
          >
            {t('chat.profile.changeImage')}
          </Button>
        </div>
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            void saveName(event);
          }}
        >
          <label htmlFor="assistant-profile-name" className="text-small font-medium">
            {t('chat.profile.name')}
          </label>
          <Input
            id="assistant-profile-name"
            value={draftName}
            maxLength={40}
            required
            autoComplete="off"
            onChange={(event) => {
              setDraft(event.target.value);
            }}
          />
          <Button type="submit" disabled={conversationId === null || busy}>
            {t('chat.profile.saveName')}
          </Button>
        </form>
        {profile.isError && (
          <p role="alert" className="text-small text-risk-text">
            {t('chat.profile.loadError')}{' '}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                void profile.refetch();
              }}
            >
              {t('common.retry')}
            </Button>
          </p>
        )}
        {actionError !== null && (
          <p role="alert" className="text-small text-risk-text">
            {actionError}
          </p>
        )}
      </Sheet.Content>
    </Sheet.Root>
  );
}
