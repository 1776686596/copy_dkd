import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ServiceDeskAssistDraft,
  ServiceDeskSessionDetail,
  ServiceDeskSession,
} from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import MessageTimeline from './MessageTimeline';
import QuickReplyPanel from './QuickReplyPanel';

function formatDateTime(value?: string | null) {
  if (!value) return '--';
  return new Date(value).toLocaleString();
}

interface SessionDetailProps {
  session: ServiceDeskSession | null;
  onRefresh: (showError?: boolean) => Promise<void>;
}

export default function SessionDetail({
  session,
  onRefresh,
}: SessionDetailProps) {
  const { t } = useTranslation();
  const [claiming, setClaiming] = useState(false);
  const [generatingDraft, setGeneratingDraft] = useState(false);
  const [releasing, setReleasing] = useState(false);
  const [returningToAi, setReturningToAi] = useState(false);
  const [sending, setSending] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [assistDraft, setAssistDraft] = useState<ServiceDeskAssistDraft | null>(
    null,
  );
  const [detail, setDetail] = useState<ServiceDeskSessionDetail | null>(null);

  const detailSession = detail?.session ?? session;

  const detailRows = useMemo(() => {
    if (!detailSession) return [];

    return [
      [t('serviceDesk.workbench.sessionId'), detailSession.session_id],
      [t('serviceDesk.workbench.pipeline'), detailSession.pipeline_uuid],
      [t('serviceDesk.workbench.sourceEntry'), detailSession.source_entry_id],
      [t('serviceDesk.workbench.externalUser'), detailSession.external_user_id],
      [
        t('serviceDesk.workbench.claimedBy'),
        detailSession.claimed_by_user_name || '--',
      ],
      [
        t('serviceDesk.workbench.updatedAt'),
        formatDateTime(detailSession.updated_at),
      ],
      [
        t('serviceDesk.workbench.handoffReason'),
        detailSession.handoff_reason || '--',
      ],
      [
        t('serviceDesk.workbench.botName'),
        detail?.bot.name || detail?.bot.uuid || '--',
      ],
    ];
  }, [detail, detailSession, t]);

  const canReply = session?.queue_status === 'manual';
  const canRelease = session?.queue_status === 'manual';
  const canReturnToAi = session?.queue_status !== 'ai';

  useEffect(() => {
    setReplyText('');
    setAssistDraft(null);
    setDetail(null);
  }, [session?.session_id]);

  useEffect(() => {
    if (!session) {
      setDetail(null);
      return;
    }

    let active = true;

    const loadDetail = async () => {
      setDetailLoading(true);
      try {
        const resp = await httpClient.getServiceDeskSessionDetail(
          session.session_id,
        );
        if (!active) return;
        setDetail(resp);
      } catch (error) {
        console.error('Failed to load service desk session detail:', error);
        if (active) {
          toast.error(t('serviceDesk.workbench.detailLoadError'));
        }
      } finally {
        if (active) {
          setDetailLoading(false);
        }
      }
    };

    void loadDetail();

    return () => {
      active = false;
    };
  }, [session, t]);

  const handleClaim = async () => {
    if (!session) return;
    setClaiming(true);
    try {
      await httpClient.claimServiceDeskSession(session.session_id);
      toast.success(t('serviceDesk.workbench.claimSuccess'));
      await onRefresh();
    } catch (error) {
      console.error('Failed to claim service desk session:', error);
      toast.error(t('serviceDesk.workbench.claimError'));
    } finally {
      setClaiming(false);
    }
  };

  const handleReply = async () => {
    if (!session || !replyText.trim() || !canReply) return;
    setSending(true);
    try {
      await httpClient.replyServiceDeskSession(
        session.session_id,
        replyText.trim(),
      );
      setReplyText('');
      toast.success(t('serviceDesk.workbench.replySuccess'));
      await onRefresh();
    } catch (error) {
      console.error('Failed to reply service desk session:', error);
      toast.error(t('serviceDesk.workbench.replyError'));
    } finally {
      setSending(false);
    }
  };

  const handleGenerateAssistDraft = async () => {
    if (!session) return;
    setGeneratingDraft(true);
    try {
      await httpClient.setServiceDeskSessionMode(
        session.session_id,
        'ai_assist',
      );
      const resp = await httpClient.generateServiceDeskAssistDraft(
        session.session_id,
      );
      setAssistDraft(resp.draft);
      setReplyText(resp.draft.reply_text);
      toast.success(t('serviceDesk.workbench.assistDraftSuccess'));
      await onRefresh(false);
    } catch (error) {
      console.error('Failed to generate assist draft:', error);
      toast.error(t('serviceDesk.workbench.assistDraftError'));
    } finally {
      setGeneratingDraft(false);
    }
  };

  const handleRelease = async () => {
    if (!session || !canRelease) return;
    setReleasing(true);
    try {
      await httpClient.releaseServiceDeskSession(session.session_id);
      setReplyText('');
      setAssistDraft(null);
      toast.success(t('serviceDesk.workbench.releaseSuccess'));
      await onRefresh();
    } catch (error) {
      console.error('Failed to release service desk session:', error);
      toast.error(t('serviceDesk.workbench.releaseError'));
    } finally {
      setReleasing(false);
    }
  };

  const handleReturnToAi = async () => {
    if (!session || !canReturnToAi) return;
    setReturningToAi(true);
    try {
      await httpClient.returnServiceDeskSessionToAi(session.session_id);
      setReplyText('');
      setAssistDraft(null);
      toast.success(t('serviceDesk.workbench.returnToAiSuccess'));
      await onRefresh();
    } catch (error) {
      console.error('Failed to return session to AI:', error);
      toast.error(t('serviceDesk.workbench.returnToAiError'));
    } finally {
      setReturningToAi(false);
    }
  };

  if (!session) {
    return (
      <Card className="flex min-h-[420px] flex-col justify-center rounded-3xl border-dashed">
        <CardHeader className="items-center text-center">
          <CardTitle>{t('serviceDesk.workbench.noSessionSelected')}</CardTitle>
          <CardDescription className="max-w-md">
            {t('serviceDesk.workbench.noSessionSelectedDescription')}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card className="flex flex-col rounded-3xl">
      <CardHeader className="border-b">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle>{t('serviceDesk.workbench.detailTitle')}</CardTitle>
            <CardDescription>
              {t('serviceDesk.workbench.detailDescription')}
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">
              {t(`serviceDesk.queueStatus.${session.queue_status}`)}
            </Badge>
            <Badge variant="secondary">
              {t(`serviceDesk.mode.${session.mode}`)}
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-6 pt-6">
        <div className="grid gap-3 md:grid-cols-2">
          {detailRows.map(([label, value]) => (
            <div
              key={label}
              className="rounded-2xl border border-border/70 bg-muted/25 px-4 py-3"
            >
              <div className="text-xs text-muted-foreground">{label}</div>
              <div className="mt-1 break-all text-sm font-medium">{value}</div>
            </div>
          ))}
        </div>

        <div className="space-y-3 rounded-2xl border border-border/70 bg-background/70 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="text-sm font-medium">
                {t('serviceDesk.workbench.claimAction')}
              </div>
              <div className="text-xs text-muted-foreground">
                {t('serviceDesk.workbench.claimHint')}
              </div>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() => void handleClaim()}
              disabled={claiming || session.queue_status === 'manual'}
            >
              {t('serviceDesk.workbench.claimAction')}
            </Button>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => void handleRelease()}
              disabled={!canRelease || releasing}
            >
              {t('serviceDesk.workbench.releaseAction')}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void handleReturnToAi()}
              disabled={!canReturnToAi || returningToAi}
            >
              {t('serviceDesk.workbench.returnToAiAction')}
            </Button>
          </div>
        </div>

        <div className="space-y-3 rounded-2xl border border-border/70 bg-background/70 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="text-sm font-medium">
                {t('serviceDesk.workbench.assistDraftTitle')}
              </div>
              <div className="text-xs text-muted-foreground">
                {t('serviceDesk.workbench.assistDraftHint')}
              </div>
            </div>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void handleGenerateAssistDraft()}
              disabled={generatingDraft}
            >
              {t('serviceDesk.workbench.generateAssistDraft')}
            </Button>
          </div>
          {assistDraft ? (
            <div className="rounded-2xl border border-dashed border-border/70 bg-muted/20 px-4 py-3">
              <div className="text-xs text-muted-foreground">
                {t('serviceDesk.workbench.assistDraftBadge')}
              </div>
              <div className="mt-1 whitespace-pre-wrap text-sm">
                {assistDraft.reply_text}
              </div>
            </div>
          ) : null}
        </div>

        <div className="space-y-3 rounded-2xl border border-border/70 bg-background/70 p-4">
          <div className="space-y-1">
            <div className="text-sm font-medium">
              {t('serviceDesk.workbench.timelineTitle')}
            </div>
            <div className="text-xs text-muted-foreground">
              {detailLoading
                ? t('common.loading')
                : t('serviceDesk.workbench.timelineDescription')}
            </div>
          </div>
          <MessageTimeline
            items={detail?.messages || []}
            emptyText={t('serviceDesk.workbench.noTimeline')}
          />
        </div>

        <div className="space-y-3 rounded-2xl border border-border/70 bg-background/70 p-4">
          <div className="space-y-1">
            <div className="text-sm font-medium">
              {t('serviceDesk.workbench.sendReply')}
            </div>
            <div className="text-xs text-muted-foreground">
              {canReply
                ? t('serviceDesk.workbench.replyPlaceholder')
                : t('serviceDesk.workbench.claimHint')}
            </div>
          </div>
          <QuickReplyPanel
            botUuid={session.bot_uuid}
            onInsert={(value) => {
              setReplyText((prev) => (prev ? `${prev}\n${value}` : value));
            }}
          />
          <Textarea
            rows={7}
            value={replyText}
            onChange={(event) => setReplyText(event.target.value)}
            placeholder={t('serviceDesk.workbench.replyPlaceholder')}
            disabled={!canReply || sending}
          />
          <div className="flex justify-end">
            <Button
              type="button"
              onClick={() => void handleReply()}
              disabled={!canReply || !replyText.trim() || sending}
            >
              {t('serviceDesk.workbench.sendReply')}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
