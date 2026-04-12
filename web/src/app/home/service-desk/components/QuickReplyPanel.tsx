import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ServiceDeskQuickReply } from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { toast } from 'sonner';

interface QuickReplyPanelProps {
  botUuid: string;
  onInsert: (value: string) => void;
}

export default function QuickReplyPanel({
  botUuid,
  onInsert,
}: QuickReplyPanelProps) {
  const { t } = useTranslation();
  const [items, setItems] = useState<ServiceDeskQuickReply[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;

    const loadQuickReplies = async () => {
      if (!botUuid) {
        setItems([]);
        return;
      }

      setLoading(true);
      try {
        const resp = await httpClient.getServiceDeskQuickReplies(botUuid);
        if (active) {
          setItems(resp.items);
        }
      } catch (error) {
        console.error('Failed to load quick replies:', error);
        if (active) {
          toast.error(t('serviceDesk.workbench.quickRepliesLoadError'));
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void loadQuickReplies();

    return () => {
      active = false;
    };
  }, [botUuid, t]);

  return (
    <Card className="rounded-2xl border border-border/70 bg-background/70">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">
          {t('serviceDesk.workbench.quickRepliesTitle')}
        </CardTitle>
        <CardDescription>
          {loading
            ? t('common.loading')
            : t('serviceDesk.workbench.quickRepliesDescription')}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {items.length === 0 ? (
          <div className="rounded-2xl border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
            {t('serviceDesk.workbench.noQuickReplies')}
          </div>
        ) : null}
        {items.map((item) => (
          <button
            key={item.uuid}
            type="button"
            onClick={() => onInsert(item.reply_text)}
            className="w-full rounded-2xl border border-border/70 px-4 py-3 text-left transition-colors hover:border-primary/40 hover:bg-accent/35"
          >
            <div className="text-sm font-medium">{item.title}</div>
            <div className="mt-1 line-clamp-3 text-xs text-muted-foreground">
              {item.reply_text}
            </div>
          </button>
        ))}
      </CardContent>
    </Card>
  );
}
