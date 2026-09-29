import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { GlassBox } from '@/features/glass-box';
import { BackIcon, Button } from '@/shared/ui';

/**
 * The glass box on its own route, full width: for the video, and for reading a finished conversation. There is no
 * chat beside it, so no linked selection is provided.
 */
export function GlassBoxPage() {
  const { t } = useTranslation();
  const { conversationId = '' } = useParams();
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Button asChild variant="ghost" size="sm">
          <Link to={`/?conversation=${encodeURIComponent(conversationId)}`}>
            <BackIcon aria-hidden="true" size={16} />
            {t('chat.backToChat')}
          </Link>
        </Button>
      </div>
      <GlassBox.Standalone conversationId={conversationId} />
    </div>
  );
}
