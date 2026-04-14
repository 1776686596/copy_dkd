import { useCallback, useEffect, useState } from 'react';
import { Plus, Boxes } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { ModelProvider } from '@/app/infra/entities/api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import ProviderForm from './component/provider-form/ProviderForm';
import { ProviderCard } from './components';
import { ExtraArg, ModelType, TestResult, ProviderModels } from './types';
import { CustomApiError } from '@/app/infra/entities/common';
import { getVisibleProviders } from './visibleProviders.js';

interface ModelsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function convertExtraArgsToObject(
  args: ExtraArg[],
): Record<string, string | number | boolean> {
  const obj: Record<string, string | number | boolean> = {};
  args.forEach((arg) => {
    if (arg.key.trim()) {
      if (arg.type === 'number') obj[arg.key] = Number(arg.value);
      else if (arg.type === 'boolean') obj[arg.key] = arg.value === 'true';
      else obj[arg.key] = arg.value;
    }
  });
  return obj;
}

export default function ModelsDialog({
  open,
  onOpenChange,
}: ModelsDialogProps) {
  const { t } = useTranslation();

  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [expandedProviders, setExpandedProviders] = useState<Set<string>>(
    new Set(),
  );
  const [providerModels, setProviderModels] = useState<
    Record<string, ProviderModels>
  >({});
  const [loadingProviders, setLoadingProviders] = useState<Set<string>>(
    new Set(),
  );

  // Provider form modal
  const [providerFormOpen, setProviderFormOpen] = useState(false);
  const [editingProviderId, setEditingProviderId] = useState<string | null>(
    null,
  );

  // Popover states
  const [addModelPopoverOpen, setAddModelPopoverOpen] = useState<string | null>(
    null,
  );
  const [editModelPopoverOpen, setEditModelPopoverOpen] = useState<
    string | null
  >(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState<string | null>(
    null,
  );

  // Form states
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  const visibleProviders: ModelProvider[] = getVisibleProviders(providers);

  const loadProviders = useCallback(async () => {
    try {
      const resp = await httpClient.getModelProviders();
      setProviders(resp.providers);
    } catch (err) {
      console.error('Failed to load providers', err);
      toast.error(t('models.loadError'));
    }
  }, [t]);

  const loadProviderModels = useCallback(
    async (providerUuid: string, silent = false) => {
      if (loadingProviders.has(providerUuid)) return;

      if (!silent) {
        setLoadingProviders((prev) => new Set(prev).add(providerUuid));
      }
      try {
        const [llmResp, embeddingResp] = await Promise.all([
          httpClient.getProviderLLMModels(providerUuid),
          httpClient.getProviderEmbeddingModels(providerUuid),
        ]);
        setProviderModels((prev) => ({
          ...prev,
          [providerUuid]: {
            llm: llmResp.models,
            embedding: embeddingResp.models,
          },
        }));
      } catch (err) {
        console.error('Failed to load models', err);
      } finally {
        if (!silent) {
          setLoadingProviders((prev) => {
            const next = new Set(prev);
            next.delete(providerUuid);
            return next;
          });
        }
      }
    },
    [loadingProviders],
  );

  useEffect(() => {
    if (open) {
      void loadProviders();
    }
  }, [loadProviders, open]);

  function toggleProvider(providerUuid: string) {
    setExpandedProviders((prev) => {
      const next = new Set(prev);
      if (next.has(providerUuid)) {
        next.delete(providerUuid);
      } else {
        next.add(providerUuid);
        if (!providerModels[providerUuid]) {
          loadProviderModels(providerUuid);
        }
      }
      return next;
    });
  }

  function handleCreateProvider() {
    setEditingProviderId(null);
    setProviderFormOpen(true);
  }

  function handleEditProvider(providerId: string) {
    setEditingProviderId(providerId);
    setProviderFormOpen(true);
  }

  async function handleDeleteProvider(providerId: string) {
    try {
      await httpClient.deleteModelProvider(providerId);
      toast.success(t('models.providerDeleted'));
      loadProviders();
    } catch (err) {
      toast.error(t('models.providerDeleteError') + (err as Error).message);
    }
  }

  async function handleAddModel(
    providerUuid: string,
    modelType: ModelType,
    name: string,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) {
    if (!name.trim()) {
      toast.error(t('models.modelNameRequired'));
      return;
    }
    setIsSubmitting(true);
    try {
      const extraArgsObj = convertExtraArgsToObject(extraArgs);

      if (modelType === 'llm') {
        await httpClient.createProviderLLMModel({
          name,
          provider_uuid: providerUuid,
          abilities,
          extra_args: extraArgsObj,
        } as never);
      } else {
        await httpClient.createProviderEmbeddingModel({
          name,
          provider_uuid: providerUuid,
          extra_args: extraArgsObj,
        } as never);
      }
      setAddModelPopoverOpen(null);
      loadProviderModels(providerUuid, true);
      loadProviders();
    } catch (err) {
      toast.error(t('models.createError') + (err as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleUpdateModel(
    providerUuid: string,
    modelId: string,
    modelType: ModelType,
    name: string,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) {
    if (!name.trim()) {
      toast.error(t('models.modelNameRequired'));
      return;
    }
    setIsSubmitting(true);
    try {
      const extraArgsObj = convertExtraArgsToObject(extraArgs);

      if (modelType === 'llm') {
        await httpClient.updateProviderLLMModel(modelId, {
          name,
          provider_uuid: providerUuid,
          abilities,
          extra_args: extraArgsObj,
        } as never);
      } else {
        await httpClient.updateProviderEmbeddingModel(modelId, {
          name,
          provider_uuid: providerUuid,
          extra_args: extraArgsObj,
        } as never);
      }
      setEditModelPopoverOpen(null);
      loadProviderModels(providerUuid, true);
      loadProviders();
    } catch (err) {
      toast.error(t('models.saveError') + (err as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteModel(
    providerUuid: string,
    modelId: string,
    modelType: ModelType,
  ) {
    try {
      if (modelType === 'llm') {
        await httpClient.deleteProviderLLMModel(modelId);
      } else {
        await httpClient.deleteProviderEmbeddingModel(modelId);
      }
      toast.success(t('models.deleteSuccess'));
      loadProviderModels(providerUuid, true);
      loadProviders();
    } catch (err) {
      toast.error(t('models.deleteError') + (err as Error).message);
    }
  }

  async function handleTestModel(
    providerUuid: string,
    name: string,
    modelType: ModelType,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) {
    setIsTesting(true);
    setTestResult(null);
    const startTime = Date.now();
    try {
      const extraArgsObj = convertExtraArgsToObject(extraArgs);

      // Get the provider info
      const provider = providers.find((p) => p.uuid === providerUuid);
      const providerData = {
        requester: provider?.requester || '',
        base_url: provider?.base_url || '',
        api_keys: provider?.api_keys || [],
      };

      if (modelType === 'llm') {
        await httpClient.testLLMModel('_', {
          uuid: '',
          name,
          provider_uuid: '',
          provider: providerData,
          abilities,
          extra_args: extraArgsObj,
        } as never);
      } else {
        await httpClient.testEmbeddingModel('_', {
          uuid: '',
          name,
          provider_uuid: '',
          provider: providerData,
          extra_args: extraArgsObj,
        } as never);
      }
      const duration = Date.now() - startTime;
      setTestResult({ success: true, duration });
    } catch (err) {
      console.error('Failed to test model', err);
      toast.error(t('models.testError') + ': ' + (err as CustomApiError).msg);
      setTestResult(null);
    } finally {
      setIsTesting(false);
    }
  }

  function handleFormClose() {
    setProviderFormOpen(false);
    loadProviders();
    // Refresh expanded providers
    expandedProviders.forEach((uuid) => loadProviderModels(uuid));
  }

  function renderProviderCard(provider: ModelProvider) {
    return (
      <ProviderCard
        key={provider.uuid}
        provider={provider}
        isExpanded={expandedProviders.has(provider.uuid)}
        isLoading={loadingProviders.has(provider.uuid)}
        models={providerModels[provider.uuid]}
        addModelPopoverOpen={addModelPopoverOpen}
        editModelPopoverOpen={editModelPopoverOpen}
        deleteConfirmOpen={deleteConfirmOpen}
        onToggle={() => toggleProvider(provider.uuid)}
        onEditProvider={() => handleEditProvider(provider.uuid)}
        onDeleteProvider={() => handleDeleteProvider(provider.uuid)}
        onOpenAddModel={() => setAddModelPopoverOpen(provider.uuid)}
        onCloseAddModel={() => setAddModelPopoverOpen(null)}
        onAddModel={(modelType, name, abilities, extraArgs) =>
          handleAddModel(provider.uuid, modelType, name, abilities, extraArgs)
        }
        onOpenEditModel={(modelId) => setEditModelPopoverOpen(modelId)}
        onCloseEditModel={() => setEditModelPopoverOpen(null)}
        onUpdateModel={(modelId, modelType, name, abilities, extraArgs) =>
          handleUpdateModel(
            provider.uuid,
            modelId,
            modelType,
            name,
            abilities,
            extraArgs,
          )
        }
        onOpenDeleteConfirm={(modelId) => setDeleteConfirmOpen(modelId)}
        onCloseDeleteConfirm={() => setDeleteConfirmOpen(null)}
        onDeleteModel={(modelId, modelType) =>
          handleDeleteModel(provider.uuid, modelId, modelType)
        }
        onTestModel={(name, modelType, abilities, extraArgs) =>
          handleTestModel(provider.uuid, name, modelType, abilities, extraArgs)
        }
        isSubmitting={isSubmitting}
        isTesting={isTesting}
        testResult={testResult}
        onResetTestResult={() => setTestResult(null)}
      />
    );
  }

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(newOpen) => {
          if (!newOpen && providerFormOpen) return;
          onOpenChange(newOpen);
        }}
      >
        <DialogContent className="overflow-hidden p-0 h-[80vh] flex flex-col !max-w-[37rem]">
          <DialogHeader className="px-6 pt-6 pb-0 flex-shrink-0">
            <DialogTitle>{t('models.title')}</DialogTitle>
          </DialogHeader>

          <div className="flex-1 overflow-auto px-6 pb-6 mt-0">
            {/* Add Provider Button */}
            <div className="mb-3 flex justify-between items-center sticky top-0 bg-background py-2 z-10">
              <span className="text-sm text-muted-foreground">
                {visibleProviders.length === 0
                  ? t('models.addProviderHintSimple')
                  : t('models.providerCount', {
                      count: visibleProviders.length,
                    })}
              </span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleCreateProvider}
                >
                  <Plus className="h-4 w-4 mr-1" />
                  {t('models.addProvider')}
                </Button>
              </div>
            </div>

            {/* Provider List */}
            {visibleProviders.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Boxes className="h-12 w-12 mb-3 opacity-50" />
                <p className="text-sm">{t('models.noProviders')}</p>
              </div>
            ) : (
              visibleProviders.map((provider) => renderProviderCard(provider))
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={providerFormOpen} onOpenChange={setProviderFormOpen}>
        <DialogContent className="w-[600px] p-6">
          <DialogHeader>
            <DialogTitle>
              {editingProviderId
                ? t('models.editProvider')
                : t('models.addProvider')}
            </DialogTitle>
          </DialogHeader>
          <ProviderForm
            providerId={editingProviderId || undefined}
            onFormSubmit={handleFormClose}
            onFormCancel={() => setProviderFormOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </>
  );
}
