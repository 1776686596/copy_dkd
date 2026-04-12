import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ServiceDeskQueueStatus,
  ServiceDeskSession,
} from '@/app/infra/entities/api';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';

function formatDateTime(value?: string | null) {
  if (!value) return '--';
  return new Date(value).toLocaleString();
}

function compactId(value: string) {
  if (value.length <= 22) return value;
  return `${value.slice(0, 10)}...${value.slice(-8)}`;
}

interface SessionListProps {
  sessions: ServiceDeskSession[];
  total: number;
  loading: boolean;
  selectedSessionId: string | null;
  onSelect: (sessionId: string) => void;
}

const GROUP_ORDER: ServiceDeskQueueStatus[] = [
  'pending_manual',
  'manual',
  'silent',
  'ai',
];

export default function SessionList({
  sessions,
  total,
  loading,
  selectedSessionId,
  onSelect,
}: SessionListProps) {
  const { t } = useTranslation();
  const groupedSessions = useMemo(() => {
    return sessions.reduce<Record<string, ServiceDeskSession[]>>(
      (acc, session) => {
        const key = session.queue_status;
        acc[key] = acc[key] || [];
        acc[key].push(session);
        return acc;
      },
      {},
    );
  }, [sessions]);

  return (
    <Card className="flex h-full min-h-0 flex-col gap-0 overflow-hidden">
      <CardHeader className="border-b">
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle>{t('serviceDesk.workbench.sessionsTitle')}</CardTitle>
            <CardDescription>
              {t('serviceDesk.workbench.sessionsDescription')}
            </CardDescription>
          </div>
          <Badge variant="outline">{total}</Badge>
        </div>
      </CardHeader>

      <CardContent className="min-h-0 flex-1 px-0">
        <ScrollArea className="h-full">
          <div className="space-y-3 p-4">
            {!loading && sessions.length === 0 && (
              <div className="rounded-2xl border border-dashed px-4 py-10 text-center text-sm text-muted-foreground">
                {t('serviceDesk.workbench.noSessions')}
              </div>
            )}

            {GROUP_ORDER.map((groupKey) => {
              const items = groupedSessions[groupKey] || [];
              if (items.length === 0) return null;

              return (
                <section key={groupKey} className="space-y-3">
                  <div className="flex items-center justify-between gap-3 px-1">
                    <div className="text-sm font-medium">
                      {t(`serviceDesk.queueStatus.${groupKey}`)}
                    </div>
                    <Badge variant="outline">{items.length}</Badge>
                  </div>
                  {items.map((session) => {
                    const isActive = session.session_id === selectedSessionId;
                    return (
                      <button
                        key={session.session_id}
                        type="button"
                        onClick={() => onSelect(session.session_id)}
                        className={cn(
                          'w-full rounded-2xl border p-4 text-left transition-colors',
                          isActive
                            ? 'border-primary bg-primary/5 shadow-sm'
                            : 'border-border/70 hover:border-primary/40 hover:bg-accent/35',
                        )}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1">
                            <div className="font-medium">
                              {compactId(session.session_id)}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {session.external_user_id}
                            </div>
                          </div>
                          <div className="flex flex-col items-end gap-2">
                            <Badge variant="outline">
                              {t(
                                `serviceDesk.queueStatus.${session.queue_status}`,
                              )}
                            </Badge>
                            <Badge variant="secondary">
                              {t(`serviceDesk.mode.${session.mode}`)}
                            </Badge>
                          </div>
                        </div>

                        <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                          <div>
                            {t('serviceDesk.workbench.claimedBy')}:{' '}
                            {session.claimed_by_user_name || '--'}
                          </div>
                          <div>
                            {t('serviceDesk.workbench.updatedAt')}:{' '}
                            {formatDateTime(session.updated_at)}
                          </div>
                        </div>

                        {session.handoff_reason && (
                          <div className="mt-3 rounded-xl bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
                            {t('serviceDesk.workbench.handoffReason')}:{' '}
                            {session.handoff_reason}
                          </div>
                        )}
                      </button>
                    );
                  })}
                </section>
              );
            })}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
