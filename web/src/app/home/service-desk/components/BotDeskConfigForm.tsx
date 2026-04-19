import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bot,
  ServiceDeskBotConfig,
  WecomPrivateContactConfig,
  WecomPrivateReceptionConfig,
} from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
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
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';

type ServiceDeskBot = Bot & { uuid: string };

interface BotDeskConfigFormProps {
  bot: ServiceDeskBot | null;
  configs: ServiceDeskBotConfig[];
  onSaved: () => Promise<void>;
}

interface ConfigDraft {
  versionLabel: string;
  handoffKeywords: string;
  manualTimeoutSeconds: number;
  enabled: boolean;
}

interface ReceptionConfigDraft {
  receptionEnabled: boolean;
  welcomeEnabled: boolean;
  fallbackReplyText: string;
  bindingRequiredFields: string;
  bindingTriggerKeywords: string;
  bindingPromptText: string;
  humanHandoffDirectEnabled: boolean;
}

const DEFAULT_PRIVATE_CONTACT_STATE = 'dkd_phase1_entry';
const DEFAULT_BINDING_REQUIRED_FIELDS = ['uid', 'server'];

function formatDateTime(value?: string | null) {
  if (!value) return '--';
  return new Date(value).toLocaleString();
}

function buildDraft(
  bot: ServiceDeskBot | null,
  config: ServiceDeskBotConfig | undefined,
): ConfigDraft {
  if (!bot) {
    return {
      versionLabel: '',
      handoffKeywords: '',
      manualTimeoutSeconds: 900,
      enabled: true,
    };
  }

  return {
    versionLabel: config?.version_label || `${bot.name} / v1`,
    handoffKeywords: (config?.handoff_keywords || []).join('\n'),
    manualTimeoutSeconds: config?.manual_timeout_seconds ?? 900,
    enabled: config?.enabled ?? true,
  };
}

function splitTextareaValues(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(/[\n,]/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

function buildReceptionDraft(
  config?: WecomPrivateReceptionConfig | null,
): ReceptionConfigDraft {
  const requiredFields = config?.binding_required_fields?.length
    ? config.binding_required_fields
    : DEFAULT_BINDING_REQUIRED_FIELDS;

  return {
    receptionEnabled: config?.reception_enabled ?? true,
    welcomeEnabled: config?.welcome_enabled ?? true,
    fallbackReplyText: config?.fallback_reply_text ?? '',
    bindingRequiredFields: requiredFields.join('\n'),
    bindingTriggerKeywords: (config?.binding_trigger_keywords ?? []).join('\n'),
    bindingPromptText: config?.binding_prompt_text ?? '',
    humanHandoffDirectEnabled: config?.human_handoff_direct_enabled ?? true,
  };
}

export default function BotDeskConfigForm({
  bot,
  configs,
  onSaved,
}: BotDeskConfigFormProps) {
  const { t } = useTranslation();
  const [saving, setSaving] = useState(false);
  const [contactConfigs, setContactConfigs] = useState<WecomPrivateContactConfig[]>([]);
  const [contactConfigsLoading, setContactConfigsLoading] = useState(false);
  const [contactRemark, setContactRemark] = useState('');
  const [contactState, setContactState] = useState(DEFAULT_PRIVATE_CONTACT_STATE);
  const [followUserId, setFollowUserId] = useState('');
  const [syncingContactConfig, setSyncingContactConfig] = useState(false);
  const [receptionConfigLoading, setReceptionConfigLoading] = useState(false);

  const currentConfig = useMemo(() => {
    if (!bot) return undefined;
    return configs.find((item) => item.bot_uuid === bot.uuid);
  }, [bot, configs]);

  const isWecomPrivateBot = bot?.adapter === 'wecomprivate';
  const primaryContactConfig = useMemo(
    () => contactConfigs.find((item) => item.is_primary) ?? null,
    [contactConfigs],
  );

  const [draft, setDraft] = useState<ConfigDraft>(() =>
    buildDraft(bot, currentConfig),
  );
  const [receptionDraft, setReceptionDraft] = useState<ReceptionConfigDraft>(() =>
    buildReceptionDraft(),
  );

  useEffect(() => {
    setDraft(buildDraft(bot, currentConfig));
  }, [bot, currentConfig]);

  useEffect(() => {
    if (!bot || bot.adapter !== 'wecomprivate') {
      setReceptionDraft(buildReceptionDraft());
      return;
    }

    let active = true;

    const loadReceptionConfig = async () => {
      setReceptionConfigLoading(true);
      try {
        const resp = await httpClient.getWecomPrivateReceptionConfig(bot.uuid);
        if (!active) return;
        setReceptionDraft(buildReceptionDraft(resp.config));
      } catch (error) {
        console.error('Failed to load wecom private reception config:', error);
        if (active) {
          toast.error(t('serviceDesk.config.wecomPrivate.receptionLoadError'));
        }
      } finally {
        if (active) {
          setReceptionConfigLoading(false);
        }
      }
    };

    void loadReceptionConfig();

    return () => {
      active = false;
    };
  }, [bot, t]);

  useEffect(() => {
    if (!bot || bot.adapter !== 'wecomprivate') {
      setContactConfigs([]);
      setContactRemark('');
      setContactState(DEFAULT_PRIVATE_CONTACT_STATE);
      setFollowUserId('');
      return;
    }

    let active = true;

    const applyContactConfigState = (items: WecomPrivateContactConfig[]) => {
      const primary = items.find((item) => item.is_primary) ?? null;
      setContactConfigs(items);
      setContactRemark(primary?.remark ?? `${bot.name} 固定二维码`);
      setContactState(primary?.state ?? DEFAULT_PRIVATE_CONTACT_STATE);
      setFollowUserId(primary?.follow_user_ids?.[0] ?? '');
    };

    const loadContactConfigs = async () => {
      setContactConfigsLoading(true);
      try {
        const resp = await httpClient.getWecomPrivateContactConfigs(bot.uuid);
        if (!active) return;
        applyContactConfigState(resp.items ?? []);
      } catch (error) {
        console.error('Failed to load wecom private contact configs:', error);
        if (active) {
          toast.error(t('serviceDesk.config.wecomPrivate.loadError'));
        }
      } finally {
        if (active) {
          setContactConfigsLoading(false);
        }
      }
    };

    void loadContactConfigs();

    return () => {
      active = false;
    };
  }, [bot, t]);

  const handleSave = async () => {
    if (!bot) return;
    setSaving(true);
    try {
      await httpClient.updateServiceDeskBotConfig(bot.uuid, {
        version_label: draft.versionLabel.trim() || `${bot.name} / v1`,
        handoff_keywords: draft.handoffKeywords
          .split(/[\n,]/)
          .map((item) => item.trim())
          .filter(Boolean),
        manual_timeout_seconds: Number(draft.manualTimeoutSeconds || 0),
        enabled: draft.enabled,
      });

      if (isWecomPrivateBot) {
        const resp = await httpClient.updateWecomPrivateReceptionConfig(bot.uuid, {
          reception_enabled: receptionDraft.receptionEnabled,
          welcome_enabled: receptionDraft.welcomeEnabled,
          fallback_reply_text: receptionDraft.fallbackReplyText.trim(),
          binding_required_fields:
            splitTextareaValues(receptionDraft.bindingRequiredFields).length > 0
              ? splitTextareaValues(receptionDraft.bindingRequiredFields)
              : DEFAULT_BINDING_REQUIRED_FIELDS,
          binding_trigger_keywords: splitTextareaValues(
            receptionDraft.bindingTriggerKeywords,
          ),
          binding_prompt_text: receptionDraft.bindingPromptText.trim(),
          human_handoff_direct_enabled:
            receptionDraft.humanHandoffDirectEnabled,
        });
        setReceptionDraft(buildReceptionDraft(resp.config));
      }

      toast.success(t('serviceDesk.config.saveSuccess'));
      await onSaved();
    } catch (error) {
      console.error('Failed to save service desk config:', error);
      toast.error(t('serviceDesk.config.saveError'));
    } finally {
      setSaving(false);
    }
  };

  const handleSyncContactConfig = async () => {
    if (!bot || bot.adapter !== 'wecomprivate') return;

    const nextFollowUserId = followUserId.trim();
    if (!nextFollowUserId) {
      toast.error(t('serviceDesk.config.wecomPrivate.followUserRequired'));
      return;
    }

    setSyncingContactConfig(true);
    try {
      await httpClient.syncWecomPrivatePrimaryContactConfig(bot.uuid, {
        follow_user_id: nextFollowUserId,
        state: contactState.trim() || DEFAULT_PRIVATE_CONTACT_STATE,
        remark: contactRemark.trim() || `${bot.name} 固定二维码`,
      });
      const refreshed = await httpClient.getWecomPrivateContactConfigs(bot.uuid);
      setContactConfigs(refreshed.items ?? []);
      const primary = (refreshed.items ?? []).find((item) => item.is_primary);
      setContactRemark(primary?.remark ?? `${bot.name} 固定二维码`);
      setContactState(primary?.state ?? DEFAULT_PRIVATE_CONTACT_STATE);
      setFollowUserId(primary?.follow_user_ids?.[0] ?? nextFollowUserId);
      toast.success(t('serviceDesk.config.wecomPrivate.syncSuccess'));
      await onSaved();
    } catch (error) {
      console.error('Failed to sync wecom private contact config:', error);
      toast.error(t('serviceDesk.config.wecomPrivate.syncError'));
    } finally {
      setSyncingContactConfig(false);
    }
  };

  if (!bot) {
    return null;
  }

  return (
    <div className="grid h-full min-h-0 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
      <Card className="rounded-3xl">
        <CardHeader>
          <CardTitle>{t('serviceDesk.config.title')}</CardTitle>
          <CardDescription>
            {t('serviceDesk.config.description')}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          <div className="grid gap-5 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="service-desk-version">
                {t('serviceDesk.config.versionLabel')}
              </Label>
              <Input
                id="service-desk-version"
                value={draft.versionLabel}
                onChange={(event) =>
                  setDraft((prev) => ({
                    ...prev,
                    versionLabel: event.target.value,
                  }))
                }
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="service-desk-timeout">
                {t('serviceDesk.config.manualTimeoutSeconds')}
              </Label>
              <Input
                id="service-desk-timeout"
                type="number"
                min={60}
                step={60}
                value={draft.manualTimeoutSeconds}
                onChange={(event) =>
                  setDraft((prev) => ({
                    ...prev,
                    manualTimeoutSeconds: Number(event.target.value || 0),
                  }))
                }
              />
            </div>

            <div className="space-y-3 rounded-2xl border border-border/70 bg-muted/25 px-4 py-3">
              <div className="flex items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="text-sm font-medium">
                    {t('serviceDesk.config.enabled')}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {t('serviceDesk.config.enabledHint')}
                  </div>
                </div>
                <Switch
                  checked={draft.enabled}
                  onCheckedChange={(checked) =>
                    setDraft((prev) => ({ ...prev, enabled: checked }))
                  }
                />
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="service-desk-keywords">
              {t('serviceDesk.config.handoffKeywords')}
            </Label>
            <Textarea
              id="service-desk-keywords"
              rows={8}
              value={draft.handoffKeywords}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  handoffKeywords: event.target.value,
                }))
              }
              placeholder={t('serviceDesk.config.handoffKeywordsHint')}
            />
            <p className="text-xs text-muted-foreground">
              {t('serviceDesk.config.handoffKeywordsHint')}
            </p>
          </div>

          {isWecomPrivateBot ? (
            <div className="space-y-4 rounded-2xl border border-border/70 bg-muted/20 p-4">
              <div className="space-y-1">
                <div className="text-sm font-medium">
                  {t('serviceDesk.config.wecomPrivate.receptionTitle')}
                </div>
                <div className="text-xs text-muted-foreground">
                  {receptionConfigLoading
                    ? t('common.loading')
                    : t('serviceDesk.config.wecomPrivate.receptionDescription')}
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <div className="space-y-3 rounded-2xl border border-border/70 bg-background/85 px-4 py-3">
                  <div className="flex items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="text-sm font-medium">
                        {t('serviceDesk.config.wecomPrivate.receptionEnabled')}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {t(
                          'serviceDesk.config.wecomPrivate.receptionEnabledHint',
                        )}
                      </div>
                    </div>
                    <Switch
                      checked={receptionDraft.receptionEnabled}
                      disabled={receptionConfigLoading}
                      onCheckedChange={(checked) =>
                        setReceptionDraft((prev) => ({
                          ...prev,
                          receptionEnabled: checked,
                        }))
                      }
                    />
                  </div>
                </div>

                <div className="space-y-3 rounded-2xl border border-border/70 bg-background/85 px-4 py-3">
                  <div className="flex items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="text-sm font-medium">
                        {t('serviceDesk.config.wecomPrivate.welcomeEnabled')}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {t(
                          'serviceDesk.config.wecomPrivate.welcomeEnabledHint',
                        )}
                      </div>
                    </div>
                    <Switch
                      checked={receptionDraft.welcomeEnabled}
                      disabled={receptionConfigLoading}
                      onCheckedChange={(checked) =>
                        setReceptionDraft((prev) => ({
                          ...prev,
                          welcomeEnabled: checked,
                        }))
                      }
                    />
                  </div>
                </div>

                <div className="space-y-3 rounded-2xl border border-border/70 bg-background/85 px-4 py-3 md:col-span-2 xl:col-span-1">
                  <div className="flex items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="text-sm font-medium">
                        {t(
                          'serviceDesk.config.wecomPrivate.humanHandoffDirectEnabled',
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {t(
                          'serviceDesk.config.wecomPrivate.humanHandoffDirectEnabledHint',
                        )}
                      </div>
                    </div>
                    <Switch
                      checked={receptionDraft.humanHandoffDirectEnabled}
                      disabled={receptionConfigLoading}
                      onCheckedChange={(checked) =>
                        setReceptionDraft((prev) => ({
                          ...prev,
                          humanHandoffDirectEnabled: checked,
                        }))
                      }
                    />
                  </div>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="wecom-binding-required-fields">
                    {t('serviceDesk.config.wecomPrivate.bindingRequiredFields')}
                  </Label>
                  <Textarea
                    id="wecom-binding-required-fields"
                    rows={4}
                    value={receptionDraft.bindingRequiredFields}
                    disabled={receptionConfigLoading}
                    onChange={(event) =>
                      setReceptionDraft((prev) => ({
                        ...prev,
                        bindingRequiredFields: event.target.value,
                      }))
                    }
                    placeholder={t(
                      'serviceDesk.config.wecomPrivate.bindingRequiredFieldsPlaceholder',
                    )}
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('serviceDesk.config.wecomPrivate.bindingRequiredFieldsHint')}
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="wecom-binding-trigger-keywords">
                    {t('serviceDesk.config.wecomPrivate.bindingTriggerKeywords')}
                  </Label>
                  <Textarea
                    id="wecom-binding-trigger-keywords"
                    rows={4}
                    value={receptionDraft.bindingTriggerKeywords}
                    disabled={receptionConfigLoading}
                    onChange={(event) =>
                      setReceptionDraft((prev) => ({
                        ...prev,
                        bindingTriggerKeywords: event.target.value,
                      }))
                    }
                    placeholder={t(
                      'serviceDesk.config.wecomPrivate.bindingTriggerKeywordsPlaceholder',
                    )}
                  />
                  <p className="text-xs text-muted-foreground">
                    {t(
                      'serviceDesk.config.wecomPrivate.bindingTriggerKeywordsHint',
                    )}
                  </p>
                </div>
              </div>

              <div className="grid gap-4">
                <div className="space-y-2">
                  <Label htmlFor="wecom-binding-prompt-text">
                    {t('serviceDesk.config.wecomPrivate.bindingPromptText')}
                  </Label>
                  <Textarea
                    id="wecom-binding-prompt-text"
                    rows={4}
                    value={receptionDraft.bindingPromptText}
                    disabled={receptionConfigLoading}
                    onChange={(event) =>
                      setReceptionDraft((prev) => ({
                        ...prev,
                        bindingPromptText: event.target.value,
                      }))
                    }
                    placeholder={t(
                      'serviceDesk.config.wecomPrivate.bindingPromptTextPlaceholder',
                    )}
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('serviceDesk.config.wecomPrivate.bindingPromptTextHint')}
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="wecom-fallback-reply-text">
                    {t('serviceDesk.config.wecomPrivate.fallbackReplyText')}
                  </Label>
                  <Textarea
                    id="wecom-fallback-reply-text"
                    rows={3}
                    value={receptionDraft.fallbackReplyText}
                    disabled={receptionConfigLoading}
                    onChange={(event) =>
                      setReceptionDraft((prev) => ({
                        ...prev,
                        fallbackReplyText: event.target.value,
                      }))
                    }
                    placeholder={t(
                      'serviceDesk.config.wecomPrivate.fallbackReplyTextPlaceholder',
                    )}
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('serviceDesk.config.wecomPrivate.fallbackReplyTextHint')}
                  </p>
                </div>
              </div>
            </div>
          ) : null}

          <div className="flex justify-end">
            <Button
              type="button"
              onClick={() => void handleSave()}
              disabled={saving}
            >
              {saving ? t('common.saving') : t('common.save')}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="rounded-3xl">
        <CardHeader>
          <CardTitle>{bot.name}</CardTitle>
          <CardDescription>{bot.description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-2xl border border-border/70 bg-muted/25 px-4 py-3">
            <div className="text-xs text-muted-foreground">
              {t('serviceDesk.config.adapterType')}
            </div>
            <div className="mt-1 text-sm font-medium">{bot.adapter}</div>
          </div>

          <div className="rounded-2xl border border-border/70 bg-muted/25 px-4 py-3">
            <div className="text-xs text-muted-foreground">
              {t('serviceDesk.config.pipelineBinding')}
            </div>
            <div className="mt-1 break-all text-sm font-medium">
              {bot.use_pipeline_name || bot.use_pipeline_uuid || '--'}
            </div>
          </div>

          <div className="rounded-2xl border border-border/70 bg-muted/25 px-4 py-3">
            <div className="text-xs text-muted-foreground">UUID</div>
            <div className="mt-1 break-all text-sm font-medium">{bot.uuid}</div>
          </div>

          {isWecomPrivateBot ? (
            <div className="space-y-4 rounded-2xl border border-amber-200/80 bg-amber-50/80 px-4 py-4">
              <div className="space-y-1">
                <div className="text-sm font-medium text-amber-950">
                  {t('serviceDesk.config.wecomPrivate.title')}
                </div>
                <div className="text-xs text-amber-900/80">
                  {t('serviceDesk.config.wecomPrivate.description')}
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="private-follow-user-id">
                  {t('serviceDesk.config.wecomPrivate.followUserId')}
                </Label>
                <Input
                  id="private-follow-user-id"
                  value={followUserId}
                  onChange={(event) => setFollowUserId(event.target.value)}
                  placeholder="zhangsan"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="private-contact-state">
                  {t('serviceDesk.config.wecomPrivate.contactState')}
                </Label>
                <Input
                  id="private-contact-state"
                  value={contactState}
                  onChange={(event) => setContactState(event.target.value)}
                  placeholder={DEFAULT_PRIVATE_CONTACT_STATE}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="private-contact-remark">
                  {t('serviceDesk.config.wecomPrivate.contactRemark')}
                </Label>
                <Input
                  id="private-contact-remark"
                  value={contactRemark}
                  onChange={(event) => setContactRemark(event.target.value)}
                  placeholder={`${bot.name} 固定二维码`}
                />
              </div>

              <div className="flex justify-end">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void handleSyncContactConfig()}
                  disabled={syncingContactConfig || contactConfigsLoading}
                >
                  {syncingContactConfig
                    ? t('serviceDesk.config.wecomPrivate.syncingAction')
                    : t('serviceDesk.config.wecomPrivate.syncAction')}
                </Button>
              </div>

              <div className="rounded-2xl border border-amber-200/70 bg-background/85 p-3">
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground">
                    {t('serviceDesk.config.wecomPrivate.qrPreview')}
                  </div>
                  {contactConfigsLoading ? (
                    <div className="text-sm text-muted-foreground">
                      {t('common.loading')}
                    </div>
                  ) : primaryContactConfig?.qr_code_url ? (
                    <div className="space-y-3">
                      <div className="flex justify-center rounded-xl border border-dashed border-amber-200 bg-white p-3">
                        <img
                          src={primaryContactConfig.qr_code_url}
                          alt={t('serviceDesk.config.wecomPrivate.qrPreview')}
                          className="h-48 w-48 rounded-lg object-contain"
                        />
                      </div>
                      <div className="space-y-1 text-xs text-muted-foreground">
                        <div>
                          {t('serviceDesk.config.wecomPrivate.primaryState')} ·{' '}
                          <span className="font-medium text-foreground">
                            {primaryContactConfig.state}
                          </span>
                        </div>
                        <div>
                          {t('serviceDesk.config.wecomPrivate.lastSynced')} ·{' '}
                          <span className="font-medium text-foreground">
                            {formatDateTime(primaryContactConfig.updated_at)}
                          </span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-sm text-muted-foreground">
                      {t('serviceDesk.config.wecomPrivate.emptyQr')}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
