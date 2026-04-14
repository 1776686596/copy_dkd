import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bot,
  ServiceDeskBotConfig,
  ServiceDeskSession,
} from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  Card,
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
  Bot as BotIcon,
  Clock3,
  Headset,
  MessageSquareReply,
} from 'lucide-react';
import { toast } from 'sonner';
import SessionList from './components/SessionList';
import SessionDetail from './components/SessionDetail';
import BotDeskConfigForm from './components/BotDeskConfigForm';
import MaterialManager from './components/MaterialManager';
import SessionFilters from './components/SessionFilters';

type ServiceDeskBot = Bot & { uuid: string };
type ServiceDeskQueueFilter = ServiceDeskSession['queue_status'] | 'all';

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

export default function ServiceDeskContent() {
  const { t } = useTranslation();
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

  return (
    <div className="flex h-full flex-col gap-4">
      <section className="relative overflow-hidden rounded-3xl border border-border/70 bg-[linear-gradient(135deg,rgba(34,136,238,0.08),rgba(255,255,255,0.98)_42%,rgba(16,185,129,0.08))] px-6 py-6">
        <div className="absolute inset-y-0 right-0 w-56 bg-[radial-gradient(circle_at_top_right,rgba(34,136,238,0.16),transparent_68%)]" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-2xl space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/80 px-3 py-1 text-xs font-medium text-muted-foreground">
              <Headset className="size-3.5 text-primary" />
              {t('serviceDesk.wecomOnlyHint')}
            </div>
            <div className="space-y-1">
              <h1 className="text-2xl font-semibold tracking-tight">
                {t('serviceDesk.heroTitle')}
              </h1>
              <p className="max-w-xl text-sm leading-6 text-muted-foreground">
                {t('serviceDesk.heroDescription')}
              </p>
            </div>
          </div>

          <div className="flex flex-col items-start gap-3 lg:min-w-[240px]">
            <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              {t('serviceDesk.workbench.selectBot')}
            </span>
            <Select value={selectedBotUuid} onValueChange={setSelectedBotUuid}>
              <SelectTrigger className="w-full min-w-[220px] bg-background/90">
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

        <div className="relative mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-border/60 bg-background/82 p-4 shadow-sm backdrop-blur">
            <div className="text-xs text-muted-foreground">
              {t('serviceDesk.summary.selectedBot')}
            </div>
            <div className="mt-2 flex items-center gap-2 text-base font-semibold">
              <BotIcon className="size-4 text-primary" />
              <span className="truncate">
                {selectedBot?.name ?? t('common.none')}
              </span>
            </div>
          </div>
          <div className="rounded-2xl border border-border/60 bg-background/82 p-4 shadow-sm backdrop-blur">
            <div className="text-xs text-muted-foreground">
              {t('serviceDesk.summary.queueTotal')}
            </div>
            <div className="mt-2 text-2xl font-semibold">{sessionsTotal}</div>
          </div>
          <div className="rounded-2xl border border-border/60 bg-background/82 p-4 shadow-sm backdrop-blur">
            <div className="text-xs text-muted-foreground">
              {t('serviceDesk.summary.manualActive')}
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <MessageSquareReply className="size-5 text-emerald-600" />
              {currentQueueStats.manual}
            </div>
          </div>
          <div className="rounded-2xl border border-border/60 bg-background/82 p-4 shadow-sm backdrop-blur">
            <div className="text-xs text-muted-foreground">
              {t('serviceDesk.summary.pendingActive')}
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <Clock3 className="size-5 text-amber-600" />
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

          <div className="grid min-h-0 flex-1 gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
            <SessionList
              sessions={sessions}
              total={sessionsTotal}
              loading={sessionsLoading}
              selectedSessionId={selectedSessionId}
              onSelect={setSelectedSessionId}
            />
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
