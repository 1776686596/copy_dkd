import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { ServiceDeskTimelineMessage } from '@/app/infra/entities/api';
import { MessageContentRenderer } from '@/app/home/monitoring/components/MessageContentRenderer';

function formatDateTime(value?: string) {
  if (!value) return '--';
  return new Date(value).toLocaleString();
}

interface MessageTimelineProps {
  items: ServiceDeskTimelineMessage[];
  emptyText: string;
}

export default function MessageTimeline({
  items,
  emptyText,
}: MessageTimelineProps) {
  const { t } = useTranslation();
  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => {
      const left = a.timestamp ? new Date(a.timestamp).getTime() : 0;
      const right = b.timestamp ? new Date(b.timestamp).getTime() : 0;
      return left - right;
    });
  }, [items]);

  return (
    <div className="space-y-4">
      {sortedItems.length === 0 ? (
        <div className="rounded-2xl border border-dashed px-4 py-10 text-center text-sm text-muted-foreground">
          {emptyText}
        </div>
      ) : null}

      {sortedItems.map((item) => {
        const isAssistant = item.role === 'assistant';
        const roleLabel = isAssistant
          ? t('serviceDesk.workbench.timelineAssistant')
          : t('serviceDesk.workbench.timelineUser');

        return (
          <div
            key={item.id}
            className={`flex ${isAssistant ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[88%] rounded-[24px] px-4 py-3 shadow-sm ${
                isAssistant
                  ? 'bg-primary text-primary-foreground'
                  : 'border border-border/70 bg-muted/20 text-foreground'
              }`}
            >
              <div
                className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] ${
                  isAssistant
                    ? 'text-primary-foreground/80'
                    : 'text-muted-foreground'
                }`}
              >
                <span className="font-medium">{roleLabel}</span>
                {item.user_name ? <span>{item.user_name}</span> : null}
                <span>{formatDateTime(item.timestamp)}</span>
              </div>
              <div className="mt-2 break-words text-sm leading-6">
                <MessageContentRenderer
                  content={item.message_content}
                  maxLines={0}
                />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
