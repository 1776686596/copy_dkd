import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Bot, ServiceDeskMaterial } from '@/app/infra/entities/api';
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
import { ScrollArea } from '@/components/ui/scroll-area';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';

type ServiceDeskBot = Bot & { uuid: string };

interface MaterialManagerProps {
  bot: ServiceDeskBot | null;
}

interface MaterialDraft {
  materialType: string;
  title: string;
  triggerKeywords: string;
  replyText: string;
  priority: number;
  enabled: boolean;
}

const INITIAL_DRAFT: MaterialDraft = {
  materialType: 'quick_reply',
  title: '',
  triggerKeywords: '',
  replyText: '',
  priority: 100,
  enabled: true,
};

export default function MaterialManager({ bot }: MaterialManagerProps) {
  const { t } = useTranslation();
  const [materials, setMaterials] = useState<ServiceDeskMaterial[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState<MaterialDraft>(INITIAL_DRAFT);

  const loadMaterials = useCallback(
    async (showError = true) => {
      if (!bot) {
        setMaterials([]);
        return;
      }

      setLoading(true);
      try {
        const resp = await httpClient.getServiceDeskMaterials(bot.uuid);
        setMaterials(resp.items);
      } catch (error) {
        console.error('Failed to load service desk materials:', error);
        if (showError) {
          toast.error(t('common.error'));
        }
      } finally {
        setLoading(false);
      }
    },
    [bot, t],
  );

  useEffect(() => {
    void loadMaterials();
  }, [loadMaterials]);

  const handleCreate = async () => {
    if (!bot) return;
    setCreating(true);
    try {
      await httpClient.createServiceDeskMaterial(bot.uuid, {
        material_type: draft.materialType.trim() || 'quick_reply',
        title: draft.title.trim(),
        trigger_keywords: draft.triggerKeywords
          .split(/[\n,]/)
          .map((item) => item.trim())
          .filter(Boolean),
        reply_text: draft.replyText.trim(),
        payload: {},
        priority: Number(draft.priority || 0),
        enabled: draft.enabled,
      });
      toast.success(t('serviceDesk.materials.createSuccess'));
      setDraft(INITIAL_DRAFT);
      await loadMaterials(false);
    } catch (error) {
      console.error('Failed to create service desk material:', error);
      toast.error(t('serviceDesk.materials.createError'));
    } finally {
      setCreating(false);
    }
  };

  if (!bot) {
    return (
      <Card className="rounded-3xl border-dashed">
        <CardHeader>
          <CardTitle>{t('serviceDesk.materials.title')}</CardTitle>
          <CardDescription>
            {t('serviceDesk.materials.noBotHint')}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="grid h-full min-h-0 gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Card className="flex min-h-0 flex-col rounded-3xl">
        <CardHeader>
          <CardTitle>{t('serviceDesk.materials.existingTitle')}</CardTitle>
          <CardDescription>
            {t('serviceDesk.materials.description')}
          </CardDescription>
        </CardHeader>
        <CardContent className="min-h-0 flex-1 px-0">
          <ScrollArea className="h-full">
            <div className="space-y-3 px-6 pb-6">
              {!loading && materials.length === 0 && (
                <div className="rounded-2xl border border-dashed px-4 py-10 text-center text-sm text-muted-foreground">
                  {t('serviceDesk.materials.empty')}
                </div>
              )}

              {materials.map((material) => (
                <div
                  key={material.uuid}
                  className="rounded-2xl border border-border/70 bg-muted/20 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="font-medium">{material.title}</div>
                      <div className="text-xs text-muted-foreground">
                        {material.material_type}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Badge variant="outline">
                        {t('serviceDesk.materials.priority')}{' '}
                        {material.priority}
                      </Badge>
                      <Badge
                        variant={material.enabled ? 'default' : 'secondary'}
                      >
                        {material.enabled
                          ? t('common.enable')
                          : t('common.close')}
                      </Badge>
                    </div>
                  </div>

                  {material.trigger_keywords.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {material.trigger_keywords.map((keyword) => (
                        <Badge key={keyword} variant="secondary">
                          {keyword}
                        </Badge>
                      ))}
                    </div>
                  )}

                  <div className="mt-3 rounded-xl bg-background/80 px-3 py-3 text-sm leading-6">
                    {material.reply_text}
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      <Card className="rounded-3xl">
        <CardHeader>
          <CardTitle>{t('serviceDesk.materials.formTitle')}</CardTitle>
          <CardDescription>
            {t('serviceDesk.materials.materialTypeHint')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="service-desk-material-type">
              {t('serviceDesk.materials.materialType')}
            </Label>
            <Input
              id="service-desk-material-type"
              value={draft.materialType}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  materialType: event.target.value,
                }))
              }
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="service-desk-material-title">
              {t('serviceDesk.materials.materialTitle')}
            </Label>
            <Input
              id="service-desk-material-title"
              value={draft.title}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  title: event.target.value,
                }))
              }
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="service-desk-material-keywords">
              {t('serviceDesk.materials.triggerKeywords')}
            </Label>
            <Textarea
              id="service-desk-material-keywords"
              rows={4}
              value={draft.triggerKeywords}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  triggerKeywords: event.target.value,
                }))
              }
              placeholder={t('serviceDesk.materials.triggerKeywordsHint')}
            />
            <p className="text-xs text-muted-foreground">
              {t('serviceDesk.materials.triggerKeywordsHint')}
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="service-desk-material-reply">
              {t('serviceDesk.materials.replyText')}
            </Label>
            <Textarea
              id="service-desk-material-reply"
              rows={8}
              value={draft.replyText}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  replyText: event.target.value,
                }))
              }
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="service-desk-material-priority">
              {t('serviceDesk.materials.priority')}
            </Label>
            <Input
              id="service-desk-material-priority"
              type="number"
              value={draft.priority}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  priority: Number(event.target.value || 0),
                }))
              }
            />
          </div>

          <div className="flex items-center justify-between rounded-2xl border border-border/70 bg-muted/25 px-4 py-3">
            <div className="space-y-1">
              <div className="text-sm font-medium">
                {t('serviceDesk.materials.enabled')}
              </div>
              <div className="text-xs text-muted-foreground">{bot.name}</div>
            </div>
            <Switch
              checked={draft.enabled}
              onCheckedChange={(checked) =>
                setDraft((prev) => ({ ...prev, enabled: checked }))
              }
            />
          </div>

          <div className="flex justify-end">
            <Button
              type="button"
              onClick={() => void handleCreate()}
              disabled={
                creating || !draft.title.trim() || !draft.replyText.trim()
              }
            >
              {creating
                ? t('common.saving')
                : t('serviceDesk.materials.createAction')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
