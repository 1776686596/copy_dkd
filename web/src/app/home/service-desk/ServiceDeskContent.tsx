import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bot,
  ServiceDeskBotConfig,
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
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  ArrowLeft,
  Clock3,
  Headset,
  MessageSquareReply,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import SessionList from './components/SessionList';
import SessionDetail from './components/SessionDetail';
import BotDeskConfigForm from './components/BotDeskConfigForm';
import MaterialManager from './components/MaterialManager';
import SessionFilters from './components/SessionFilters';

type ServiceDeskBot = Bot & { uuid: string };
type ServiceDeskQueueFilter = ServiceDeskSession['queue_status'] | 'all';
type ServiceDeskViewMode = 'overview' | 'workspace';

const QUEUE_FILTERS: ServiceDeskQueueFilter[] = [
  'all',
  'pending_manual',
  'manual',
  'silent',
  'ai',
];

function isServiceDeskBot(bot: Bot): bot is ServiceDeskBot {
  return Boolean(bot.uuid) && ['wecomcs', 'lark'].includes(bot.adapter);
}

function getChannelLabel(adapter: string, t: ReturnType<typeof useTranslation>['t']) {
  if (adapter === 'lark') {
    return t('serviceDesk.channels.lark');
  }
  return t('serviceDesk.channels.wecomcs');
}

function getChannelBadgeClass(adapter: string) {
  if (adapter === 'lark') {
    return 'border-sky-200 bg-sky-50 text-sky-700';
  }
  return 'border-emerald-200 bg-emerald-50 text-emerald-700';
}

function getChannelSurfaceClass(adapter: string) {
  if (adapter === 'lark') {
    return 'bg-[linear-gradient(160deg,rgba(240,249,255,0.98),rgba(255,255,255,0.94)_45%,rgba(224,242,254,0.88))]';
  }
  return 'bg-[linear-gradient(160deg,rgba(240,253,244,0.98),rgba(255,255,255,0.94)_45%,rgba(220,252,231,0.88))]';
}

export default function ServiceDeskContent() {
  const { t } = useTranslation();
  const [viewMode, setViewMode] = useState<ServiceDeskViewMode>('overview');
  const [activeTab, setActiveTab] = useState('workbench');
  const [bots, setBots] = useState<ServiceDeskBot[]>([]);
  const [configs, setConfigs] = useState<ServiceDeskBotConfig[]>([]);
  const [selectedBotUuid, setSelectedBotUuid] = useState('');
  const [queueFilter, setQueueFilter] = useState<ServiceDeskQueueFilter>('all');
  const [searchKeyword, setSearchKeyword] = useState('');
  const [claimedByFilter, setClaimedByFilter] = useState('all');
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
    null,
  );
  const [sessions, setSessions] = useState<ServiceDeskSession[]>([]);
  const [sessionsTotal, setSessionsTotal] = useState(0);
  const [bootstrapping, setBootstrapping] = useState(true);
  const [sessionsLoading, setSessionsLoading] = useState(false);

  const loadBootstrapData = useCallback(async () => {
    setBootstrapping(true);
    try {
      const [botsResp, configsResp] = await Promise.all([
        httpClient.getBots(),
        httpClient.getServiceDeskBotConfigs(),
      ]);
      setBots(botsResp.bots.filter(isServiceDeskBot));
      setConfigs(configsResp.items);
    } catch (error) {
      console.error('Failed to load service desk bootstrap data:', error);
      toast.error(t('common.error'));
    } finally {
      setBootstrapping(false);
    }
  }, [t]);

  useEffect(() => {
    void loadBootstrapData();
  }, [loadBootstrapData]);

  useEffect(() => {
    if (bots.length === 0) {
      setSelectedBotUuid('');
      return;
    }

    if (!bots.some((bot) => bot.uuid === selectedBotUuid)) {
      setSelectedBotUuid(bots[0].uuid);
    }
  }, [bots, selectedBotUuid]);

  const loadSessions = useCallback(
    async (showError = true) => {
      if (!selectedBotUuid) {
        setSessions([]);
        setSessionsTotal(0);
        return;
      }

      setSessionsLoading(true);
      try {
        const resp = await httpClient.getServiceDeskSessions({
          botUuid: selectedBotUuid,
          queueStatus: queueFilter === 'all' ? undefined : queueFilter,
          claimedBy: claimedByFilter === 'all' ? undefined : claimedByFilter,
          keyword: searchKeyword.trim() || undefined,
          limit: 50,
          offset: 0,
        });
        setSessions(resp.sessions);
        setSessionsTotal(resp.total);
      } catch (error) {
        console.error('Failed to load service desk sessions:', error);
        if (showError) {
          toast.error(t('common.error'));
        }
      } finally {
        setSessionsLoading(false);
      }
    },
    [claimedByFilter, queueFilter, searchKeyword, selectedBotUuid, t],
  );

  useEffect(() => {
    if (activeTab !== 'workbench') return;
    void loadSessions();
    const timer = window.setInterval(() => {
      void loadSessions(false);
    }, 15000);
    return () => window.clearInterval(timer);
  }, [activeTab, loadSessions]);

  useEffect(() => {
    if (sessions.length === 0) {
      setSelectedSessionId(null);
      return;
    }

    if (!sessions.some((session) => session.session_id === selectedSessionId)) {
      setSelectedSessionId(sessions[0].session_id);
    }
  }, [selectedSessionId, sessions]);

  const selectedBot = useMemo(
    () => bots.find((bot) => bot.uuid === selectedBotUuid) ?? null,
    [bots, selectedBotUuid],
  );

  const selectedSession = useMemo(
    () =>
      sessions.find((session) => session.session_id === selectedSessionId) ??
      null,
    [selectedSessionId, sessions],
  );

  const currentQueueStats = useMemo(() => {
    return sessions.reduce(
      (acc, session) => {
        if (session.queue_status === 'manual') acc.manual += 1;
        if (session.queue_status === 'pending_manual') acc.pending += 1;
        return acc;
      },
      { manual: 0, pending: 0 },
    );
  }, [sessions]);

  const distinctChannelCount = useMemo(
    () => new Set(bots.map((bot) => bot.adapter)).size,
    [bots],
  );

  const overviewGridClassName = useMemo(() => {
    if (bots.length <= 1) {
      return 'grid-cols-1';
    }
    if (bots.length === 2) {
      return 'grid-cols-1 xl:grid-cols-2';
    }
    return 'grid-cols-1 md:grid-cols-2 2xl:grid-cols-3';
  }, [bots.length]);

  const openWorkspace = useCallback(
    (botUuid: string, tab: string = 'workbench') => {
      setSelectedBotUuid(botUuid);
      setActiveTab(tab);
      setViewMode('workspace');
    },
    [],
  );

  if (bootstrapping) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner text={t('common.loading')} />
      </div>
    );
  }

  if (bots.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <Card className="max-w-2xl border-dashed">
          <CardHeader>
            <CardTitle>{t('serviceDesk.noBotsTitle')}</CardTitle>
            <CardDescription>
              {t('serviceDesk.noBotsDescription')}
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  if (viewMode === 'overview') {
    return (
      <div className="flex h-full flex-col gap-6">
        <section className="rounded-[32px] border border-border/70 bg-[linear-gradient(135deg,rgba(255,255,255,0.98),rgba(247,250,252,0.95)_46%,rgba(241,245,249,0.9))] px-6 py-6 shadow-sm">
          <div className="flex flex-col gap-6 2xl:flex-row 2xl:items-end 2xl:justify-between">
            <div className="max-w-3xl space-y-3">
              <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/80 px-3 py-1 text-xs font-medium text-muted-foreground">
                <Headset className="size-3.5 text-primary" />
                {t('serviceDesk.title')}
              </div>
              <div className="space-y-2">
                <h1 className="text-3xl font-semibold tracking-tight">
                  {t('serviceDesk.overview.title')}
                </h1>
                <p className="max-w-2xl text-sm leading-7 text-muted-foreground">
                  {t('serviceDesk.overview.description')}
                </p>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 2xl:min-w-[560px]">
              <div className="rounded-2xl border border-border/70 bg-background/88 px-4 py-4">
                <div className="text-xs text-muted-foreground">
                  {t('serviceDesk.overview.botCount')}
                </div>
                <div className="mt-2 text-3xl font-semibold">{bots.length}</div>
              </div>
              <div className="rounded-2xl border border-border/70 bg-background/88 px-4 py-4">
                <div className="text-xs text-muted-foreground">
                  {t('serviceDesk.overview.channelCount')}
                </div>
                <div className="mt-2 text-3xl font-semibold">
                  {distinctChannelCount}
                </div>
              </div>
              <div className="rounded-2xl border border-border/70 bg-background/88 px-4 py-4">
                <div className="text-xs text-muted-foreground">
                  {t('serviceDesk.summary.selectedBot')}
                </div>
                <div className="mt-2 truncate text-lg font-semibold">
                  {selectedBot?.name ?? bots[0]?.name ?? t('common.none')}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className={cn('grid auto-rows-fr gap-4', overviewGridClassName)}>
          {bots.map((bot) => {
            const botConfig =
              configs.find((item) => item.bot_uuid === bot.uuid) ?? null;
            const channelLabel = getChannelLabel(bot.adapter, t);
            const channelBadgeClass = getChannelBadgeClass(bot.adapter);
            const channelSurfaceClass = getChannelSurfaceClass(bot.adapter);

            return (
              <Card
                key={bot.uuid}
                className={cn(
                  'relative overflow-hidden rounded-[32px] border-border/70 shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40',
                  channelSurfaceClass,
                )}
              >
                <div className="absolute inset-y-0 right-0 w-40 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.86),transparent_68%)]" />
                <CardHeader className="relative space-y-5 pb-4">
                  <div className="flex items-start justify-between gap-3">
                    <Badge
                      variant="outline"
                      className={channelBadgeClass}
                    >
                      {channelLabel}
                    </Badge>
                    <Badge variant="secondary">
                      {botConfig?.enabled
                        ? t('serviceDesk.overview.ruleEnabled')
                        : t('serviceDesk.overview.ruleDisabled')}
                    </Badge>
                  </div>
                  <div className="space-y-3">
                    <CardTitle className="text-2xl">{bot.name}</CardTitle>
                    <CardDescription className="min-h-12 max-w-xl text-sm leading-7 text-muted-foreground">
                      {bot.description || t('serviceDesk.heroDescription')}
                    </CardDescription>
                  </div>
                </CardHeader>
                <CardContent className="relative flex h-full flex-col gap-5 pt-0">
                  <div className="grid gap-3 xl:grid-cols-2">
                    <div className="rounded-2xl border border-border/70 bg-background/78 px-4 py-4">
                      <div className="text-xs text-muted-foreground">
                        {t('serviceDesk.config.pipelineBinding')}
                      </div>
                      <div className="mt-2 break-all text-sm font-medium leading-6">
                        {bot.use_pipeline_name ||
                          bot.use_pipeline_uuid ||
                          t('common.none')}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-border/70 bg-background/78 px-4 py-4">
                      <div className="text-xs text-muted-foreground">
                        {t('serviceDesk.config.adapterType')}
                      </div>
                      <div className="mt-2 text-sm font-medium">
                        {channelLabel}
                      </div>
                    </div>
                  </div>

                  <div className="mt-auto flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="lg"
                      onClick={() => openWorkspace(bot.uuid, 'workbench')}
                    >
                      {t('serviceDesk.overview.enterWorkbench')}
                    </Button>
                    <Button
                      type="button"
                      size="lg"
                      variant="outline"
                      onClick={() => openWorkspace(bot.uuid, 'bot-config')}
                    >
                      {t('serviceDesk.overview.openRules')}
                    </Button>
                    <Button
                      type="button"
                      size="lg"
                      variant="ghost"
                      onClick={() => openWorkspace(bot.uuid, 'materials')}
                    >
                      {t('serviceDesk.overview.openMaterials')}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </section>
      </div>
    );
  }

  const selectedChannelLabel = selectedBot
    ? getChannelLabel(selectedBot.adapter, t)
    : t('common.none');

  return (
    <div className="flex h-full flex-col gap-4">
      <section className="rounded-[28px] border border-border/70 bg-background px-5 py-5 shadow-sm">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="space-y-3">
            <Button
              type="button"
              variant="ghost"
              className="h-auto px-0 text-muted-foreground"
              onClick={() => setViewMode('overview')}
            >
              <ArrowLeft className="size-4" />
              {t('serviceDesk.overview.backToOverview')}
            </Button>
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-semibold tracking-tight">
                  {selectedBot?.name ?? t('common.none')}
                </h1>
                <Badge
                  variant="outline"
                  className={getChannelBadgeClass(selectedBot?.adapter || '')}
                >
                  {selectedChannelLabel}
                </Badge>
              </div>
              <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
                {selectedBot?.description || t('serviceDesk.heroDescription')}
              </p>
            </div>
          </div>

          <div className="flex min-w-[220px] flex-col gap-2">
            <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              {t('serviceDesk.workbench.selectBot')}
            </span>
            <Select value={selectedBotUuid} onValueChange={setSelectedBotUuid}>
              <SelectTrigger className="w-full bg-background">
                <SelectValue
                  placeholder={t('serviceDesk.workbench.selectBot')}
                />
              </SelectTrigger>
              <SelectContent>
                {bots.map((bot) => (
                  <SelectItem key={bot.uuid} value={bot.uuid}>
                    {bot.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <div className="rounded-2xl border border-border/70 bg-muted/20 px-4 py-3">
            <div className="text-xs text-muted-foreground">
              {t('serviceDesk.summary.queueTotal')}
            </div>
            <div className="mt-1 text-2xl font-semibold">{sessionsTotal}</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-muted/20 px-4 py-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <MessageSquareReply className="size-4 text-emerald-600" />
              {t('serviceDesk.summary.manualActive')}
            </div>
            <div className="mt-1 text-2xl font-semibold">
              {currentQueueStats.manual}
            </div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-muted/20 px-4 py-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Clock3 className="size-4 text-amber-600" />
              {t('serviceDesk.summary.pendingActive')}
            </div>
            <div className="mt-1 text-2xl font-semibold">
              {currentQueueStats.pending}
            </div>
          </div>
        </div>
      </section>

      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        className="flex min-h-0 flex-1 flex-col"
      >
        <TabsList className="h-11 shrink-0 p-1">
          <TabsTrigger value="workbench">
            {t('serviceDesk.tabs.workbench')}
          </TabsTrigger>
          <TabsTrigger value="bot-config">
            {t('serviceDesk.tabs.botConfig')}
          </TabsTrigger>
          <TabsTrigger value="materials">
            {t('serviceDesk.tabs.materials')}
          </TabsTrigger>
        </TabsList>

        <TabsContent
          value="workbench"
          className="mt-0 flex min-h-0 flex-1 flex-col gap-4"
        >
          <div className="grid min-h-0 flex-1 gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
            <div className="flex min-h-0 flex-col gap-4">
              <SessionFilters
                queueFilters={QUEUE_FILTERS}
                queueFilter={queueFilter}
                searchKeyword={searchKeyword}
                claimedByFilter={claimedByFilter}
                loading={sessionsLoading}
                onQueueFilterChange={setQueueFilter}
                onSearchKeywordChange={setSearchKeyword}
                onClaimedByFilterChange={setClaimedByFilter}
                onRefresh={() => void loadSessions()}
              />
              <div className="min-h-0 flex-1">
                <SessionList
                  sessions={sessions}
                  total={sessionsTotal}
                  loading={sessionsLoading}
                  selectedSessionId={selectedSessionId}
                  onSelect={setSelectedSessionId}
                />
              </div>
            </div>
            <SessionDetail session={selectedSession} onRefresh={loadSessions} />
          </div>
        </TabsContent>

        <TabsContent value="bot-config" className="mt-0 min-h-0 flex-1">
          <BotDeskConfigForm
            bot={selectedBot}
            configs={configs}
            onSaved={loadBootstrapData}
          />
        </TabsContent>

        <TabsContent value="materials" className="mt-0 min-h-0 flex-1">
          <MaterialManager bot={selectedBot} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
