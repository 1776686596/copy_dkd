import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ServiceDeskAssistDraft,
  ServiceDeskSession,
  ServiceDeskSessionDetail,
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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import MessageTimeline from './MessageTimeline';
import QuickReplyPanel from './QuickReplyPanel';
import { mergeServiceDeskTimelineMessages } from '../utils/timelineMessages.js';

const SERVICE_DESK_TIMELINE_LIMIT = 1000;

function formatDateTime(value?: string | null) {
  if (!value) return '--';
  return new Date(value).toLocaleString();
}

interface SessionDetailProps {
  session: ServiceDeskSession | null;
  onRefresh: (showError?: boolean) => Promise<void>;
  compactMode?: boolean;
  botAdapter?: string | null;
}

export default function SessionDetail({
  session,
  onRefresh,
  compactMode = false,
  botAdapter = null,
}: SessionDetailProps) {
  const { t } = useTranslation();
  const [claiming, setClaiming] = useState(false);
  const [generatingDraft, setGeneratingDraft] = useState(false);
  const [releasing, setReleasing] = useState(false);
  const [returningToAi, setReturningToAi] = useState(false);
  const [sending, setSending] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [savingBinding, setSavingBinding] = useState(false);
  const [closingSession, setClosingSession] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [bindingUid, setBindingUid] = useState('');
  const [bindingServer, setBindingServer] = useState('');
  const [bindingRoleName, setBindingRoleName] = useState('');
  const [closureRemark, setClosureRemark] = useState('');
  const [closureTags, setClosureTags] = useState('');
  const [knowledgeFeedback, setKnowledgeFeedback] = useState('');
  const [assistDraft, setAssistDraft] = useState<ServiceDeskAssistDraft | null>(
    null,
  );
  const [assistDraftVisible, setAssistDraftVisible] = useState(false);
  const [detail, setDetail] = useState<ServiceDeskSessionDetail | null>(null);

  const detailSession = detail?.session ?? session;
  const lead = detail?.lead ?? null;
  const routingDecisions = detail?.routing_decisions ?? [];
  const bindingTask = detail?.binding_task ?? null;
  const closureRecord = detail?.closure_record ?? null;
  const supportsWecomPrivateOps =
    (detail?.bot?.adapter ?? botAdapter) === 'wecomprivate';
  const isClosed =
    detailSession?.queue_status === 'closed' || closureRecord !== null;
  const canReply = detailSession?.queue_status === 'manual';
  const canRelease = detailSession?.queue_status === 'manual';
  const canReturnToAi =
    detailSession?.queue_status !== undefined &&
    !['ai', 'closed'].includes(detailSession.queue_status);

  useEffect(() => {
    setReplyText('');
    setBindingUid('');
    setBindingServer('');
    setBindingRoleName('');
    setClosureRemark('');
    setClosureTags('');
    setKnowledgeFeedback('');
    setAssistDraft(null);
    setAssistDraftVisible(false);
    setDetail(null);
  }, [session?.session_id]);

  useEffect(() => {
    setBindingUid(bindingTask?.provided_uid ?? '');
    setBindingServer(bindingTask?.provided_server ?? '');
    setBindingRoleName(bindingTask?.provided_role_name ?? '');
  }, [
    bindingTask?.id,
    bindingTask?.provided_role_name,
    bindingTask?.provided_server,
    bindingTask?.provided_uid,
  ]);

  useEffect(() => {
    if (!closureRecord) {
      return;
    }
    setClosureRemark('');
    setClosureTags((closureRecord.tag_updates?.add ?? []).join(', '));
    setKnowledgeFeedback(closureRecord.knowledge_feedback ?? '');
  }, [closureRecord]);

  useEffect(() => {
    if (!session) {
      setDetail(null);
      return;
    }

    let active = true;

    const loadDetail = async () => {
      setDetailLoading(true);
      try {
        const [resp, monitoringResp] = await Promise.all([
          httpClient.getServiceDeskSessionDetail(session.session_id),
          httpClient
            .getSessionMessages(session.session_id, SERVICE_DESK_TIMELINE_LIMIT, 0)
            .catch((error) => {
              console.error(
                'Failed to load monitoring messages for service desk session:',
                error,
              );
              return null;
            }),
        ]);
        if (!active) return;
        setDetail({
          ...resp,
          messages: mergeServiceDeskTimelineMessages(
            resp.messages,
            monitoringResp?.messages ?? [],
          ),
        });
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
    if (!session || isClosed) return;
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
    if (assistDraft && assistDraftVisible) {
      setAssistDraftVisible(false);
      return;
    }
    if (assistDraft) {
      setAssistDraftVisible(true);
      return;
    }
    setGeneratingDraft(true);
    try {
      const resp = await httpClient.generateServiceDeskAssistDraft(
        session.session_id,
      );
      setAssistDraft(resp.draft);
      setAssistDraftVisible(true);
      toast.success(t('serviceDesk.workbench.assistDraftSuccess'));
    } catch (error) {
      console.error('Failed to generate assist draft:', error);
      toast.error(t('serviceDesk.workbench.assistDraftError'));
    } finally {
      setGeneratingDraft(false);
    }
  };

  const handleInsertAssistDraft = () => {
    if (!assistDraft?.reply_text) return;
    setReplyText((prev) =>
      prev.trim()
        ? `${prev.trim()}\n${assistDraft.reply_text}`
        : assistDraft.reply_text,
    );
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

  const handleSaveBinding = async () => {
    if (!session || isClosed || !supportsWecomPrivateOps) return;
    setSavingBinding(true);
    try {
      const requestedFields =
        bindingTask?.requested_fields && bindingTask.requested_fields.length > 0
          ? bindingTask.requested_fields
          : ['uid', 'server'];
      const providedValues: Record<string, string> = {
        uid: bindingUid.trim(),
        server: bindingServer.trim(),
        role_name: bindingRoleName.trim(),
      };
      const isCompleted = requestedFields.every(
        (field) => (providedValues[field] || '').trim().length > 0,
      );
      const resp = await httpClient.upsertServiceDeskBindingTask(
        session.session_id,
        {
          requested_fields: requestedFields,
          provided_uid: providedValues.uid || undefined,
          provided_server: providedValues.server || undefined,
          provided_role_name: providedValues.role_name || undefined,
          verify_status: isCompleted ? 'completed' : 'pending',
        },
      );
      setDetail((prev) =>
        prev ? { ...prev, binding_task: resp.binding_task } : prev,
      );
      toast.success(t('serviceDesk.workbench.bindingSaveSuccess'));
    } catch (error) {
      console.error('Failed to save service desk binding task:', error);
      toast.error(t('serviceDesk.workbench.bindingSaveError'));
    } finally {
      setSavingBinding(false);
    }
  };

  const handleCloseSession = async () => {
    if (!session || isClosed || !supportsWecomPrivateOps) return;
    setClosingSession(true);
    try {
      const resp = await httpClient.closeServiceDeskSession(session.session_id, {
        resolution_type: 'answered',
        tag_updates: {
          add: closureTags
            .split(/[\n,]/)
            .map((item) => item.trim())
            .filter(Boolean),
          remove: [],
        },
        remark_text: closureRemark.trim() || undefined,
        followup_needed: false,
        knowledge_feedback: knowledgeFeedback.trim() || undefined,
      });
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              closure_record: resp.closure_record,
              session: {
                ...prev.session,
                queue_status: 'closed',
              },
            }
          : prev,
      );
      toast.success(t('serviceDesk.workbench.closeSuccess'));
      await onRefresh();
    } catch (error) {
      console.error('Failed to close service desk session:', error);
      toast.error(t('serviceDesk.workbench.closeError'));
    } finally {
      setClosingSession(false);
    }
  };

  if (!session) {
    return (
      <Card className="flex h-full min-h-0 min-h-[420px] flex-col justify-center rounded-3xl border-dashed xl:min-h-0">
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
    <Card className="flex h-full min-h-0 min-h-[560px] flex-col overflow-hidden rounded-3xl xl:min-h-0">
      <CardHeader
        className={cn(
          'border-b',
          compactMode ? 'bg-background/90 py-4' : 'bg-muted/15',
        )}
      >
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
              {t(`serviceDesk.queueStatus.${detailSession?.queue_status || session.queue_status}`)}
            </Badge>
            <Badge variant="secondary">
              {t(`serviceDesk.mode.${detailSession?.mode || session.mode}`)}
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex min-h-0 flex-1 flex-col gap-0 p-0">
        <div
          className={cn(
            'flex min-h-0 flex-1 flex-col px-6',
            compactMode ? 'gap-4 py-4' : 'gap-6 py-5',
          )}
        >
          {compactMode ? null : (
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
          )}
          <div className="min-h-0 flex-1 overflow-y-auto pr-2">
            <MessageTimeline
              items={detail?.messages || []}
              emptyText={t('serviceDesk.workbench.noTimeline')}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-3 rounded-2xl border border-border/70 bg-background/80 p-4">
              <div className="space-y-1">
                <div className="text-sm font-medium">
                  {t('serviceDesk.workbench.leadTitle')}
                </div>
                <div className="text-xs text-muted-foreground">
                  {t('serviceDesk.workbench.leadDescription')}
                </div>
              </div>
              {lead ? (
                <div className="grid gap-2 text-sm">
                  <div>
                    {t('serviceDesk.workbench.leadExternalUser')} ·{' '}
                    <span className="font-medium">{lead.external_userid}</span>
                  </div>
                  <div>
                    {t('serviceDesk.workbench.leadFollowUser')} ·{' '}
                    <span className="font-medium">{lead.follow_user_id}</span>
                  </div>
                  <div>
                    {t('serviceDesk.workbench.leadSourceState')} ·{' '}
                    <span className="font-medium">{lead.source_state || '--'}</span>
                  </div>
                  <div>
                    {t('serviceDesk.workbench.leadProfileStatus')} ·{' '}
                    <span className="font-medium">{lead.profile_status}</span>
                  </div>
                  <div>
                    {t('serviceDesk.workbench.leadTags')} ·{' '}
                    <span className="font-medium">
                      {lead.current_tags.length > 0
                        ? lead.current_tags.join(', ')
                        : '--'}
                    </span>
                  </div>
                  <div>
                    UID ·{' '}
                    <span className="font-medium">
                      {lead.bound_game_identity?.uid || '--'}
                    </span>
                  </div>
                  <div>
                    Server ·{' '}
                    <span className="font-medium">
                      {lead.bound_game_identity?.server || '--'}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">
                  {t('serviceDesk.workbench.leadEmpty')}
                </div>
              )}
            </div>

            <div className="space-y-3 rounded-2xl border border-border/70 bg-background/80 p-4">
              <div className="space-y-1">
                <div className="text-sm font-medium">
                  {t('serviceDesk.workbench.routingTitle')}
                </div>
                <div className="text-xs text-muted-foreground">
                  {t('serviceDesk.workbench.routingDescription')}
                </div>
              </div>
              {routingDecisions.length > 0 ? (
                <div className="space-y-2">
                  {routingDecisions.map((item) => (
                    <div
                      key={item.id}
                      className="rounded-xl border border-border/60 bg-muted/20 px-3 py-3 text-sm"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium">{item.decision}</span>
                        <span className="text-xs text-muted-foreground">
                          {formatDateTime(item.created_at)}
                        </span>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {item.trigger_type} · {item.trigger_reason}
                        {item.matched_rule ? ` · ${item.matched_rule}` : ''}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">
                  {t('serviceDesk.workbench.routingEmpty')}
                </div>
              )}
            </div>

            {supportsWecomPrivateOps ? (
              <>
                <div className="space-y-3 rounded-2xl border border-border/70 bg-background/80 p-4">
                  <div className="space-y-1">
                    <div className="text-sm font-medium">
                      {t('serviceDesk.workbench.bindingTitle')}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {t('serviceDesk.workbench.bindingDescription')}
                    </div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="space-y-2">
                      <Label htmlFor="binding-uid">
                        {t('serviceDesk.workbench.bindingUidLabel')}
                      </Label>
                      <Input
                        id="binding-uid"
                        value={bindingUid}
                        onChange={(event) => setBindingUid(event.target.value)}
                        placeholder={t('serviceDesk.workbench.bindingUidPlaceholder')}
                        disabled={savingBinding || isClosed}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="binding-server">
                        {t('serviceDesk.workbench.bindingServerLabel')}
                      </Label>
                      <Input
                        id="binding-server"
                        value={bindingServer}
                        onChange={(event) => setBindingServer(event.target.value)}
                        placeholder={t(
                          'serviceDesk.workbench.bindingServerPlaceholder',
                        )}
                        disabled={savingBinding || isClosed}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="binding-role-name">
                        {t('serviceDesk.workbench.bindingRoleNameLabel')}
                      </Label>
                      <Input
                        id="binding-role-name"
                        value={bindingRoleName}
                        onChange={(event) => setBindingRoleName(event.target.value)}
                        placeholder={t(
                          'serviceDesk.workbench.bindingRoleNamePlaceholder',
                        )}
                        disabled={savingBinding || isClosed}
                      />
                    </div>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-xs text-muted-foreground">
                      {bindingTask
                        ? `${t('serviceDesk.workbench.bindingStatus')} · ${bindingTask.verify_status}`
                        : t('serviceDesk.workbench.bindingEmpty')}
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void handleSaveBinding()}
                      disabled={savingBinding || isClosed}
                    >
                      {savingBinding
                        ? t('common.saving')
                        : t('serviceDesk.workbench.bindingSave')}
                    </Button>
                  </div>
                </div>

                <div className="space-y-3 rounded-2xl border border-border/70 bg-background/80 p-4">
                  <div className="space-y-1">
                    <div className="text-sm font-medium">
                      {t('serviceDesk.workbench.closureTitle')}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {t('serviceDesk.workbench.closureDescription')}
                    </div>
                  </div>
                  {closureRecord ? (
                    <div className="space-y-2 text-sm">
                      <div>
                        {t('serviceDesk.workbench.closureResolution')} ·{' '}
                        <span className="font-medium">
                          {closureRecord.resolution_type}
                        </span>
                      </div>
                      <div>
                        {t('serviceDesk.workbench.closureTags')} ·{' '}
                        <span className="font-medium">
                          {(closureRecord.tag_updates?.add ?? []).join(', ') ||
                            '--'}
                        </span>
                      </div>
                      <div>
                        {t('serviceDesk.workbench.closureOperator')} ·{' '}
                        <span className="font-medium">
                          {closureRecord.closed_by}
                        </span>
                      </div>
                      <div>
                        {t('serviceDesk.workbench.closureTime')} ·{' '}
                        <span className="font-medium">
                          {formatDateTime(closureRecord.created_at)}
                        </span>
                      </div>
                      <div>
                        {t('serviceDesk.workbench.closureFeedback')} ·{' '}
                        <span className="font-medium">
                          {closureRecord.knowledge_feedback || '--'}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <Textarea
                        rows={3}
                        value={closureTags}
                        onChange={(event) => setClosureTags(event.target.value)}
                        placeholder={t(
                          'serviceDesk.workbench.closureTagsPlaceholder',
                        )}
                        disabled={closingSession}
                      />
                      <Textarea
                        rows={3}
                        value={closureRemark}
                        onChange={(event) => setClosureRemark(event.target.value)}
                        placeholder={t(
                          'serviceDesk.workbench.closureRemarkPlaceholder',
                        )}
                        disabled={closingSession}
                      />
                      <Textarea
                        rows={3}
                        value={knowledgeFeedback}
                        onChange={(event) =>
                          setKnowledgeFeedback(event.target.value)
                        }
                        placeholder={t(
                          'serviceDesk.workbench.closureFeedbackPlaceholder',
                        )}
                        disabled={closingSession}
                      />
                      <div className="flex justify-end">
                        <Button
                          type="button"
                          onClick={() => void handleCloseSession()}
                          disabled={closingSession}
                        >
                          {closingSession
                            ? t('common.saving')
                            : t('serviceDesk.workbench.closeAction')}
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              </>
            ) : null}
          </div>
        </div>

        <div className="shrink-0 border-t bg-muted/10 px-6 py-5">
          <div className="space-y-4">
            {assistDraft && assistDraftVisible ? (
              <div className="rounded-2xl border border-amber-200 bg-amber-50/85 px-4 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-sm font-medium text-amber-950">
                      <Sparkles className="size-4 text-amber-600" />
                      {t('serviceDesk.workbench.assistDraftTitle')}
                    </div>
                    <div className="text-xs text-amber-900/80">
                      {t('serviceDesk.workbench.assistDraftHint')}
                    </div>
                  </div>
                  <Badge
                    variant="outline"
                    className="border-amber-300 bg-amber-100 text-amber-950"
                  >
                    {t('serviceDesk.workbench.assistDraftBadge')}
                  </Badge>
                </div>
                <div className="mt-3 whitespace-pre-wrap rounded-xl border border-amber-200 bg-background/85 px-4 py-3 text-sm leading-6 text-foreground/90">
                  {assistDraft.reply_text}
                </div>
                <div className="mt-4 flex flex-wrap justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setAssistDraftVisible(false)}
                  >
                    {t('common.cancel')}
                  </Button>
                  <Button type="button" onClick={handleInsertAssistDraft}>
                    {t('serviceDesk.workbench.insertAssistDraft')}
                  </Button>
                </div>
              </div>
            ) : null}

            <div className="flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-border/70 bg-background/80 p-4">
              <div className="space-y-1">
                <div className="text-sm font-medium">
                  {t('serviceDesk.workbench.sendReply')}
                </div>
                <div className="text-xs text-muted-foreground">
                  {isClosed
                    ? t('serviceDesk.workbench.closedHint')
                    : canReply
                      ? t('serviceDesk.workbench.replyPlaceholder')
                      : t('serviceDesk.workbench.claimHint')}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void handleClaim()}
                  disabled={claiming || canReply || isClosed}
                >
                  {t('serviceDesk.workbench.claimAction')}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void handleRelease()}
                  disabled={!canRelease || releasing || isClosed}
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
                  disabled={generatingDraft || isClosed}
                >
                  <Sparkles className="size-4" />
                  {t('serviceDesk.workbench.generateAssistDraft')}
                </Button>
              </div>
            </div>

            <div className="space-y-3 rounded-2xl border border-border/70 bg-background/80 p-4">
              <div className="space-y-1">
                <div className="text-sm font-medium">
                  {t('serviceDesk.workbench.quickRepliesTitle')}
                </div>
                <div className="text-xs text-muted-foreground">
                  {t('serviceDesk.workbench.quickRepliesDescription')}
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
                disabled={!canReply || sending || isClosed}
              />
              <div className="flex justify-end">
                <Button
                  type="button"
                  onClick={() => void handleReply()}
                  disabled={!canReply || !replyText.trim() || sending || isClosed}
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
