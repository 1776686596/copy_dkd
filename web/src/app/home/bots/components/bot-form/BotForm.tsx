import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import i18n from 'i18next';
import {
  IChooseAdapterEntity,
  IPipelineEntity,
} from '@/app/home/bots/components/bot-form/ChooseEntity';
import {
  DynamicFormItemConfig,
  getDefaultValues,
  parseDynamicFormItemType,
} from '@/app/home/components/dynamic-form/DynamicFormItemConfig';
import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import { UUID } from 'uuidjs';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Bot } from '@/app/infra/entities/api';
import { getAdapterDocUrl } from '@/app/infra/entities/adapter-docs';
import { ExternalLink } from 'lucide-react';
import RoutingRulesEditor from './RoutingRulesEditor';

import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { CustomApiError } from '@/app/infra/entities/common';
import {
  groupByCategory,
  getCategoryLabel,
} from '@/app/infra/entities/adapter-categories';
import { resolveWecomWebLoginUiState } from './wecomWebLoginState';

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('bots.botNameRequired') }),
    description: z.string().optional(),
    adapter: z.string().min(1, { message: t('bots.adapterRequired') }),
    adapter_config: z.record(z.string(), z.any()),
    enable: z.boolean().optional(),
    use_pipeline_uuid: z.string().optional(),
    pipeline_routing_rules: z
      .array(
        z.object({
          type: z.enum([
            'launcher_type',
            'launcher_id',
            'message_content',
            'message_has_element',
          ]),
          operator: z.enum([
            'eq',
            'neq',
            'contains',
            'not_contains',
            'starts_with',
            'regex',
          ]),
          value: z.string(),
          pipeline_uuid: z.string(),
        }),
      )
      .optional(),
  });

export default function BotForm({
  initBotId,
  onFormSubmit,
  onNewBotCreated,
  onDirtyChange,
}: {
  initBotId?: string;
  onFormSubmit: (value: z.infer<ReturnType<typeof getFormSchema>>) => void;
  onNewBotCreated: (botId: string) => void;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const { t } = useTranslation();
  const formSchema = getFormSchema(t);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: '',
      adapter: '',
      adapter_config: {},
      enable: true,
      use_pipeline_uuid: '',
      pipeline_routing_rules: [],
    },
  });

  // Track whether initial data loading is complete.
  // setValue calls during init should NOT mark the form as dirty.
  const isInitializing = useRef(true);

  const [adapterNameToDynamicConfigMap, setAdapterNameToDynamicConfigMap] =
    useState(new Map<string, IDynamicFormItemSchema[]>());
  const [showDynamicForm, setShowDynamicForm] = useState<boolean>(false);
  const [adapterNameList, setAdapterNameList] = useState<
    IChooseAdapterEntity[]
  >([]);
  const [adapterDescriptionList, setAdapterDescriptionList] = useState<
    Record<string, string>
  >({});
  const [adapterHelpLinks, setAdapterHelpLinks] = useState<
    Record<string, Record<string, string>>
  >({});

  const [pipelineNameList, setPipelineNameList] = useState<IPipelineEntity[]>(
    [],
  );

  const [dynamicFormConfigList, setDynamicFormConfigList] = useState<
    IDynamicFormItemSchema[]
  >([]);
  const [, setIsLoading] = useState<boolean>(false);
  const [webhookUrl, setWebhookUrl] = useState<string>('');
  const [extraWebhookUrl, setExtraWebhookUrl] = useState<string>('');
  const [wecomWebBotEnabled, setWecomWebBotEnabled] = useState<boolean>(false);
  const [loginRequired, setLoginRequired] = useState<boolean>(false);
  const [loginStateLoaded, setLoginStateLoaded] = useState<boolean>(false);
  const [loginStateChecked, setLoginStateChecked] = useState<boolean>(false);
  const [loginQrImageBase64, setLoginQrImageBase64] = useState<string | null>(
    null,
  );
  const [loginQrLoadError, setLoginQrLoadError] = useState<string | null>(null);
  const loginPollingRef = useRef<number | null>(null);
  const loginRequestTokenRef = useRef(0);

  // Watch adapter and adapter_config for filtering
  const currentAdapter = form.watch('adapter');
  const currentAdapterConfig = form.watch('adapter_config');

  // Group adapters by category for the Select dropdown
  const groupedAdapters = useMemo(
    () => groupByCategory(adapterNameList),
    [adapterNameList],
  );
  const setBotFormValuesRef = useRef(setBotFormValues);
  setBotFormValuesRef.current = setBotFormValues;

  // Notify parent when dirty state changes
  const { isDirty } = form.formState;
  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  useEffect(() => {
    setBotFormValuesRef.current();
  }, []);

  const clearWecomWebLoginPolling = useCallback(() => {
    if (loginPollingRef.current !== null) {
      window.clearInterval(loginPollingRef.current);
      loginPollingRef.current = null;
    }
  }, []);

  const refreshWecomWebLoginState = useCallback(
    async (botId: string, requestToken: number) => {
      try {
        const res = await httpClient.getBot(botId);
        if (loginRequestTokenRef.current !== requestToken) {
          return;
        }
        const runtimeValues = res.bot.adapter_runtime_values;
        setWecomWebBotEnabled(res.bot.enable ?? false);
        const nextLoginStateChecked =
          runtimeValues?.login_state_checked === true;
        const nextLoginRequired = runtimeValues?.login_required === true;

        setLoginStateLoaded(true);
        setLoginStateChecked(nextLoginStateChecked);
        setLoginRequired(nextLoginRequired);
        setLoginQrLoadError(null);
        setLoginQrImageBase64(
          nextLoginRequired
            ? (runtimeValues?.login_qr_image_base64 ?? null)
            : null,
        );
      } catch {
        if (loginRequestTokenRef.current !== requestToken) {
          return;
        }
        setLoginStateLoaded(true);
        setLoginQrLoadError('登录状态拉取失败，请稍后刷新页面重试');
      }
    },
    [],
  );

  useEffect(() => {
    if (!initBotId || currentAdapter !== 'wecomweb') {
      loginRequestTokenRef.current += 1;
      clearWecomWebLoginPolling();
      setWecomWebBotEnabled(false);
      setLoginStateLoaded(false);
      setLoginStateChecked(false);
      setLoginRequired(false);
      setLoginQrImageBase64(null);
      setLoginQrLoadError(null);
      return;
    }

    const botId = initBotId;
    const requestToken = loginRequestTokenRef.current + 1;
    loginRequestTokenRef.current = requestToken;
    clearWecomWebLoginPolling();
    setLoginStateLoaded(false);
    void refreshWecomWebLoginState(botId, requestToken);
    loginPollingRef.current = window.setInterval(() => {
      void refreshWecomWebLoginState(botId, requestToken);
    }, 3000);

    return () => {
      loginRequestTokenRef.current += 1;
      clearWecomWebLoginPolling();
    };
  }, [
    clearWecomWebLoginPolling,
    currentAdapter,
    initBotId,
    refreshWecomWebLoginState,
  ]);

  const wecomWebLoginUiState =
    initBotId && currentAdapter === 'wecomweb'
      ? resolveWecomWebLoginUiState({
          hasLoadedState: loginStateLoaded,
          botEnabled: wecomWebBotEnabled,
          loginStateChecked,
          loginRequired,
          loginQrImageBase64,
          loginQrLoadError,
        })
      : null;

  function setBotFormValues() {
    isInitializing.current = true;
    initBotFormComponent().then(() => {
      if (initBotId) {
        getBotConfig(initBotId)
          .then((val) => {
            // Use form.reset() to set values AND update the dirty baseline,
            // so isDirty stays false after initial load.
            form.reset({
              name: val.name,
              description: val.description,
              adapter: val.adapter,
              adapter_config: val.adapter_config,
              enable: val.enable,
              use_pipeline_uuid: val.use_pipeline_uuid || '',
              pipeline_routing_rules: val.pipeline_routing_rules || [],
            });
            handleAdapterSelect(val.adapter);

            if (val.webhook_full_url) {
              setWebhookUrl(val.webhook_full_url);
            } else {
              setWebhookUrl('');
            }
            setExtraWebhookUrl(val.extra_webhook_full_url || '');
          })
          .catch((err) => {
            toast.error(
              t('bots.getBotConfigError') + (err as CustomApiError).msg,
            );
          })
          .finally(() => {
            isInitializing.current = false;
          });
      } else {
        form.reset();
        setWebhookUrl('');
        setExtraWebhookUrl('');
        isInitializing.current = false;
      }
    });
  }

  async function initBotFormComponent() {
    const pipelinesRes = await httpClient.getPipelines();
    setPipelineNameList(
      pipelinesRes.pipelines.map((item) => {
        return {
          label: item.name,
          value: item.uuid ?? '',
          emoji: item.emoji,
        };
      }),
    );

    const adaptersRes = await httpClient.getAdapters();
    setAdapterNameList(
      adaptersRes.adapters.map((item) => {
        return {
          label: extractI18nObject(item.label),
          value: item.name,
          categories: item.spec.categories,
        };
      }),
    );

    setAdapterDescriptionList(
      adaptersRes.adapters.reduce(
        (acc, item) => {
          acc[item.name] = extractI18nObject(item.description);
          return acc;
        },
        {} as Record<string, string>,
      ),
    );

    setAdapterHelpLinks(
      adaptersRes.adapters.reduce(
        (acc, item) => {
          if (item.spec.help_links) {
            acc[item.name] = item.spec.help_links;
          }
          return acc;
        },
        {} as Record<string, Record<string, string>>,
      ),
    );

    adaptersRes.adapters.forEach((rawAdapter) => {
      adapterNameToDynamicConfigMap.set(
        rawAdapter.name,
        rawAdapter.spec.config.map(
          (item) =>
            new DynamicFormItemConfig({
              default: item.default,
              id: UUID.generate(),
              label: item.label,
              description: item.description,
              name: item.name,
              required: item.required,
              type: parseDynamicFormItemType(item.type),
              options: item.options,
              show_if: item.show_if,
            }),
        ),
      );
    });
    setAdapterNameToDynamicConfigMap(adapterNameToDynamicConfigMap);
  }

  async function getBotConfig(botId: string): Promise<
    z.infer<typeof formSchema> & {
      webhook_full_url?: string;
      extra_webhook_full_url?: string;
    }
  > {
    return new Promise((resolve, reject) => {
      httpClient
        .getBot(botId)
        .then((res) => {
          const bot = res.bot;
          const runtimeValues = bot.adapter_runtime_values;
          resolve({
            adapter: bot.adapter,
            description: bot.description,
            name: bot.name,
            adapter_config: bot.adapter_config,
            enable: bot.enable ?? true,
            use_pipeline_uuid: bot.use_pipeline_uuid ?? '',
            pipeline_routing_rules: bot.pipeline_routing_rules ?? [],
            webhook_full_url: runtimeValues?.webhook_full_url ?? undefined,
            extra_webhook_full_url:
              runtimeValues?.extra_webhook_full_url ?? undefined,
          });
        })
        .catch((err) => {
          reject(err);
        });
    });
  }

  function handleAdapterSelect(adapterName: string) {
    if (adapterName) {
      const dynamicFormConfigList =
        adapterNameToDynamicConfigMap.get(adapterName);
      if (dynamicFormConfigList) {
        setDynamicFormConfigList(dynamicFormConfigList);
        if (!initBotId) {
          form.setValue(
            'adapter_config',
            getDefaultValues(dynamicFormConfigList),
          );
        }
      }
      setShowDynamicForm(true);
    } else {
      setShowDynamicForm(false);
    }
  }

  function onDynamicFormSubmit() {
    setIsLoading(true);
    if (initBotId) {
      const updateBot: Bot = {
        uuid: initBotId,
        name: form.getValues().name,
        description: form.getValues().description ?? '',
        adapter: form.getValues().adapter,
        adapter_config: form.getValues().adapter_config,
        enable: form.getValues().enable,
        use_pipeline_uuid: form.getValues().use_pipeline_uuid,
        pipeline_routing_rules: form.getValues().pipeline_routing_rules ?? [],
      };
      httpClient
        .updateBot(initBotId, updateBot)
        .then(() => {
          // Reset dirty baseline to current values so isDirty becomes false
          form.reset(form.getValues());
          onFormSubmit(form.getValues());
          toast.success(t('bots.saveSuccess'));
        })
        .catch((err) => {
          toast.error(t('bots.saveError') + err.msg);
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      const newBot: Bot = {
        name: form.getValues().name,
        description: form.getValues().description ?? '',
        adapter: form.getValues().adapter,
        adapter_config: form.getValues().adapter_config,
        enable: form.getValues().enable,
      };
      httpClient
        .createBot(newBot)
        .then((res) => {
          toast.success(t('bots.createSuccess'));
          initBotId = res.uuid;

          setBotFormValues();

          onNewBotCreated(res.uuid);
        })
        .catch((err) => {
          toast.error(t('bots.createError') + err.msg);
        })
        .finally(() => {
          setIsLoading(false);
          form.reset();
        });
    }
  }

  return (
    <Form {...form}>
      <form
        id="bot-form"
        onSubmit={form.handleSubmit(onDynamicFormSubmit)}
        className="space-y-6"
      >
        {/* Card 1: Basic Information */}
        <Card>
          <CardHeader>
            <CardTitle>{t('bots.basicInfo')}</CardTitle>
            <CardDescription>{t('bots.basicInfoDescription')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('bots.botName')}
                    <span className="text-destructive">*</span>
                  </FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('bots.botDescription')}</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        {/* Card 2: Pipeline Binding (edit mode only) */}
        {initBotId && (
          <Card>
            <CardHeader>
              <CardTitle>{t('bots.routingConnection')}</CardTitle>
              <CardDescription>
                {t('bots.routingConnectionDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <FormField
                control={form.control}
                name="use_pipeline_uuid"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('bots.bindPipeline')}</FormLabel>
                    <FormControl>
                      <Select onValueChange={field.onChange} {...field}>
                        <SelectTrigger>
                          {field.value ? (
                            (() => {
                              const pipeline = pipelineNameList.find(
                                (p) => p.value === field.value,
                              );
                              return (
                                <div className="flex items-center gap-2">
                                  {pipeline?.emoji && (
                                    <span className="text-sm shrink-0">
                                      {pipeline.emoji}
                                    </span>
                                  )}
                                  <span>{pipeline?.label ?? field.value}</span>
                                </div>
                              );
                            })()
                          ) : (
                            <SelectValue
                              placeholder={t('bots.selectPipeline')}
                            />
                          )}
                        </SelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            {pipelineNameList.map((item) => (
                              <SelectItem key={item.value} value={item.value}>
                                <div className="flex items-center gap-2">
                                  {item.emoji && (
                                    <span className="text-sm shrink-0">
                                      {item.emoji}
                                    </span>
                                  )}
                                  <span>{item.label}</span>
                                </div>
                              </SelectItem>
                            ))}
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                    </FormControl>
                  </FormItem>
                )}
              />

              {/* Pipeline Routing Rules */}
              <RoutingRulesEditor
                form={form}
                pipelineNameList={pipelineNameList}
              />
            </CardContent>
          </Card>
        )}

        {/* Card 3: Adapter Configuration */}
        <Card>
          <CardHeader>
            <CardTitle>{t('bots.adapterConfig')}</CardTitle>
            <CardDescription>
              {t('bots.adapterConfigDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <FormField
              control={form.control}
              name="adapter"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('bots.platformAdapter')}
                    <span className="text-destructive">*</span>
                  </FormLabel>
                  <FormControl>
                    <div className="flex items-center gap-2">
                      <Select
                        onValueChange={(value) => {
                          field.onChange(value);
                          handleAdapterSelect(value);
                        }}
                        value={field.value}
                      >
                        <SelectTrigger className="w-[240px]">
                          {field.value ? (
                            <div className="flex items-center gap-2">
                              <img
                                src={httpClient.getAdapterIconURL(field.value)}
                                alt=""
                                className="h-5 w-5 rounded"
                              />
                              <span>
                                {adapterNameList.find(
                                  (a) => a.value === field.value,
                                )?.label ?? field.value}
                              </span>
                            </div>
                          ) : (
                            <SelectValue
                              placeholder={t('bots.selectAdapter')}
                            />
                          )}
                        </SelectTrigger>
                        <SelectContent>
                          {groupedAdapters.map((group) => (
                            <SelectGroup
                              key={group.categoryId ?? 'uncategorized'}
                            >
                              {group.categoryId && (
                                <SelectLabel>
                                  {getCategoryLabel(t, group.categoryId)}
                                </SelectLabel>
                              )}
                              {group.items.map((item) => (
                                <SelectItem key={item.value} value={item.value}>
                                  <div className="flex items-center gap-2">
                                    <img
                                      src={httpClient.getAdapterIconURL(
                                        item.value,
                                      )}
                                      alt=""
                                      className="h-5 w-5 rounded"
                                    />
                                    <span>{item.label}</span>
                                  </div>
                                </SelectItem>
                              ))}
                            </SelectGroup>
                          ))}
                        </SelectContent>
                      </Select>
                      {currentAdapter &&
                        (() => {
                          const docUrl = getAdapterDocUrl(
                            adapterHelpLinks[currentAdapter],
                            i18n.language,
                          );
                          return docUrl ? (
                            <a
                              href={docUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex shrink-0 items-center gap-1 text-xs text-primary hover:underline"
                            >
                              {t('bots.viewAdapterDocs')}
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          ) : null;
                        })()}
                    </div>
                  </FormControl>
                  {currentAdapter && adapterDescriptionList[currentAdapter] && (
                    <FormDescription>
                      {adapterDescriptionList[currentAdapter]}
                    </FormDescription>
                  )}
                  <FormMessage />
                </FormItem>
              )}
            />

            {showDynamicForm && dynamicFormConfigList.length > 0 && (
              <DynamicFormComponent
                itemConfigList={dynamicFormConfigList}
                initialValues={currentAdapterConfig}
                onSubmit={(values) => {
                  form.setValue('adapter_config', values, {
                    shouldDirty: !isInitializing.current,
                  });
                }}
                systemContext={{
                  webhook_url: webhookUrl,
                  extra_webhook_url: extraWebhookUrl,
                }}
              />
            )}

            {initBotId &&
              currentAdapter === 'wecomweb' &&
              wecomWebLoginUiState && (
                <div className="rounded-lg border bg-muted/20 p-4">
                  <div className="space-y-2">
                    <div>
                      <p className="text-sm font-medium">企业微信网页登录</p>
                      <p className="text-sm text-muted-foreground">
                        保持当前页面打开即可；如登录失效，会自动显示新的二维码。
                      </p>
                    </div>

                    {wecomWebLoginUiState.panelState === 'qrcode' &&
                    wecomWebLoginUiState.qrImageBase64 ? (
                      <div className="flex justify-center rounded-md bg-background p-4">
                        <img
                          src={
                            wecomWebLoginUiState.qrImageBase64
                              ? `data:image/png;base64,${wecomWebLoginUiState.qrImageBase64}`
                              : undefined
                          }
                          alt="企业微信网页登录二维码"
                          className="h-56 w-56 max-w-full"
                        />
                      </div>
                    ) : wecomWebLoginUiState.panelState === 'error' ? (
                      <p className="text-sm text-muted-foreground">
                        {loginQrLoadError}，系统会继续自动重试。
                      </p>
                    ) : wecomWebLoginUiState.panelState === 'disabled' ? (
                      <p className="text-sm text-muted-foreground">
                        当前 Bot
                        未启用；启用后才会开始检查企业微信网页登录状态。
                      </p>
                    ) : wecomWebLoginUiState.panelState === 'checking' ? (
                      <p className="text-sm text-muted-foreground">
                        正在检查当前登录状态，如需扫码会自动显示二维码。
                      </p>
                    ) : wecomWebLoginUiState.panelState === 'generating' ? (
                      <p className="text-sm text-muted-foreground">
                        正在生成登录二维码，请稍等片刻。
                      </p>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        当前已登录，无需扫码；如果登录失效，这里会自动出现二维码。
                      </p>
                    )}
                  </div>
                </div>
              )}
          </CardContent>
        </Card>
      </form>
    </Form>
  );
}
