import { useEffect, useState } from 'react';
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
    <Card className="flex min-h-[720px] flex-col overflow-hidden rounded-3xl">
      <CardHeader className="border-b bg-muted/15">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle>
                {detailSession?.external_user_id || session.session_id}
              </CardTitle>
              {detail?.bot.name || detail?.bot.uuid ? (
                <Badge variant="outline">
                  {detail?.bot.name || detail?.bot.uuid}
                </Badge>
              ) : null}
            </div>
            <CardDescription>
              {detailSession?.source_entry_id
                ? `${t('serviceDesk.workbench.sourceEntry')} · ${detailSession.source_entry_id}`
                : t('serviceDesk.workbench.detailDescription')}
            </CardDescription>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span>
                {t('serviceDesk.workbench.updatedAt')} ·{' '}
                {formatDateTime(detailSession?.updated_at)}
              </span>
              {detailSession?.claimed_by_user_name ? (
                <span>
                  {t('serviceDesk.workbench.claimedBy')} ·{' '}
                  {detailSession.claimed_by_user_name}
                </span>
              ) : null}
              {detailSession?.handoff_reason ? (
                <span>
                  {t('serviceDesk.workbench.handoffReason')} ·{' '}
                  {detailSession.handoff_reason}
                </span>
              ) : null}
            </div>
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

      <CardContent className="flex flex-1 flex-col gap-0 p-0">
        <div className="flex-1 space-y-4 px-6 py-5">
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

        <div className="border-t bg-muted/10 px-6 py-5">
          <div className="space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-border/70 bg-background/80 p-4">
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
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void handleClaim()}
                  disabled={claiming || session.queue_status === 'manual'}
                >
                  {t('serviceDesk.workbench.claimAction')}
                </Button>
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
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void handleGenerateAssistDraft()}
                  disabled={generatingDraft}
                >
                  {t('serviceDesk.workbench.generateAssistDraft')}
                </Button>
              </div>
            </div>
            {assistDraft ? (
              <div className="rounded-2xl border border-dashed border-border/70 bg-background/80 px-4 py-3">
                <div className="text-xs text-muted-foreground">
                  {t('serviceDesk.workbench.assistDraftBadge')}
                </div>
                <div className="mt-1 whitespace-pre-wrap text-sm">
                  {assistDraft.reply_text}
                </div>
              </div>
            ) : null}

            <div className="space-y-3 rounded-2xl border border-border/70 bg-background/80 p-4">
              <div className="space-y-1">
                <div className="text-sm font-medium">
                  {t('serviceDesk.workbench.assistDraftTitle')}
                </div>
                <div className="text-xs text-muted-foreground">
                  {t('serviceDesk.workbench.assistDraftHint')}
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
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
