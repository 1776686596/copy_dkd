import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Bot, ServiceDeskBotConfig } from '@/app/infra/entities/api';
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

export default function BotDeskConfigForm({
  bot,
  configs,
  onSaved,
}: BotDeskConfigFormProps) {
  const { t } = useTranslation();
  const [saving, setSaving] = useState(false);

  const currentConfig = useMemo(() => {
    if (!bot) return undefined;
    return configs.find((item) => item.bot_uuid === bot.uuid);
  }, [bot, configs]);

  const [draft, setDraft] = useState<ConfigDraft>(() =>
    buildDraft(bot, currentConfig),
  );

  useEffect(() => {
    setDraft(buildDraft(bot, currentConfig));
  }, [bot, currentConfig]);

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
      toast.success(t('serviceDesk.config.saveSuccess'));
      await onSaved();
    } catch (error) {
      console.error('Failed to save service desk config:', error);
      toast.error(t('serviceDesk.config.saveError'));
    } finally {
      setSaving(false);
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
        </CardContent>
      </Card>
    </div>
  );
}
