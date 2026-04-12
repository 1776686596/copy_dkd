import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ServiceDeskTimelineMessage } from '@/app/infra/entities/api';

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
    <ScrollArea className="max-h-[360px]">
      <div className="space-y-3">
        {sortedItems.length === 0 ? (
          <div className="rounded-2xl border border-dashed px-4 py-10 text-center text-sm text-muted-foreground">
            {emptyText}
          </div>
        ) : null}

        {sortedItems.map((item) => (
          <div
            key={item.id}
            className="rounded-2xl border border-border/70 bg-muted/20 px-4 py-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Badge variant="outline">
                  {item.role === 'assistant'
                    ? t('serviceDesk.workbench.timelineAssistant')
                    : t('serviceDesk.workbench.timelineUser')}
                </Badge>
                {item.user_name ? (
                  <span className="text-xs text-muted-foreground">
                    {item.user_name}
                  </span>
                ) : null}
              </div>
              <div className="text-xs text-muted-foreground">
                {formatDateTime(item.timestamp)}
              </div>
            </div>
            <div className="mt-3 whitespace-pre-wrap text-sm">
              {item.message_content}
            </div>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
}
