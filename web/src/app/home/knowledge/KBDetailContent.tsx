import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import KBForm from '@/app/home/knowledge/components/kb-form/KBForm';
import KBDoc from '@/app/home/knowledge/components/kb-docs/KBDoc';
import KBEntries from '@/app/home/knowledge/components/kb-entries/KBEntries';
import KBRetrieveGeneric from '@/app/home/knowledge/components/kb-retrieve/KBRetrieveGeneric';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { useTranslation } from 'react-i18next';
import { KnowledgeBase } from '@/app/infra/entities/api';
import { CustomApiError } from '@/app/infra/entities/common';
import { toast } from 'sonner';
import { FileText, FolderOpen, MessageSquareText, Search, Trash2 } from 'lucide-react';

export default function KBDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { refreshKnowledgeBases, knowledgeBases, setDetailEntityName } =
    useSidebarData();

  // 同步侧边栏详情页标题
  useEffect(() => {
    if (isCreateMode) {
      setDetailEntityName(t('knowledge.createKnowledgeBase'));
    } else {
      const kb = knowledgeBases.find((k) => k.id === id);
      setDetailEntityName(kb?.name ?? id);
    }
    return () => setDetailEntityName(null);
  }, [id, isCreateMode, knowledgeBases, setDetailEntityName, t]);

  const [activeTab, setActiveTab] = useState('metadata');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [kbInfo, setKbInfo] = useState<KnowledgeBase | null>(null);
  const [formDirty, setFormDirty] = useState(false);

  const loadKbInfo = useCallback(
    async (kbId: string) => {
      try {
        const resp = await httpClient.getKnowledgeBase(kbId);
        setKbInfo(resp.base);
      } catch (e) {
        console.error('Failed to load KB info:', e);
        toast.error(
          t('knowledge.loadKnowledgeBaseFailed') + (e as CustomApiError).msg,
        );
      }
    },
    [t],
  );

  // 读取知识库信息，用于判断能力开关
  useEffect(() => {
    if (!isCreateMode) {
      loadKbInfo(id);
    }
  }, [id, isCreateMode, loadKbInfo]);

  const hasDocumentCapability = (): boolean => {
    if (!kbInfo || !kbInfo.knowledge_engine) return false;
    return (
      kbInfo.knowledge_engine.capabilities?.includes('doc_ingestion') ?? false
    );
  };

  const isLocalFaqKnowledgeBase = (): boolean =>
    kbInfo?.knowledge_engine?.plugin_id === 'builtin/local-faq';

  function handleKbDeleted() {
    refreshKnowledgeBases();
    navigate('/home/knowledge');
  }

  function handleNewKbCreated(newKbId: string) {
    refreshKnowledgeBases();
    navigate(`/home/knowledge?id=${encodeURIComponent(newKbId)}`);
  }

  function handleKbUpdated() {
    refreshKnowledgeBases();
    loadKbInfo(id);
  }

  async function confirmDelete() {
    try {
      await httpClient.deleteKnowledgeBase(id);
      setShowDeleteConfirm(false);
      handleKbDeleted();
    } catch (e) {
      toast.error(
        t('knowledge.deleteKnowledgeBaseFailed') + (e as CustomApiError).msg,
      );
    }
  }

  const retrieveFunction = async (kbId: string, query: string) => {
    return await httpClient.retrieveKnowledgeBase(kbId, query);
  };

  const getRetrieveResultTitle = (result: {
    id: string;
    metadata: Record<string, unknown>;
  }) => {
    if (isLocalFaqKnowledgeBase()) {
      return (
        (result.metadata.matched_question as string) ||
        (result.metadata.source_file_id as string) ||
        result.id
      );
    }
    return (
      (result.metadata.document_name as string) ||
      (result.metadata.file_id as string) ||
      result.id
    );
  };

  // 创建模式
  if (isCreateMode) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">
            {t('knowledge.createKnowledgeBase')}
          </h1>
          <Button type="submit" form="kb-form">
            {t('common.submit')}
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="mx-auto max-w-3xl pb-8">
            <KBForm
              initKbId={undefined}
              onNewKbCreated={handleNewKbCreated}
              onKbUpdated={handleKbUpdated}
            />
          </div>
        </div>
      </div>
    );
  }

  // 编辑模式
  return (
    <>
      <div className="flex h-full flex-col">
        {/* 顶部操作区 */}
        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">
            {t('knowledge.editKnowledgeBase')}
          </h1>
          <Button type="submit" form="kb-form" disabled={!formDirty}>
            {t('common.save')}
          </Button>
        </div>

        {/* 标签页 */}
        <Tabs
          key={id}
          value={activeTab}
          onValueChange={setActiveTab}
          className="flex flex-1 flex-col min-h-0"
        >
          <TabsList className="shrink-0">
            <TabsTrigger value="metadata" className="gap-1.5">
              <FileText className="size-3.5" />
              {t('knowledge.metadata')}
            </TabsTrigger>
            {hasDocumentCapability() && (
              <TabsTrigger value="documents" className="gap-1.5">
                <FolderOpen className="size-3.5" />
                {t('knowledge.documents')}
              </TabsTrigger>
            )}
            {isLocalFaqKnowledgeBase() && (
              <TabsTrigger value="entries" className="gap-1.5">
                <MessageSquareText className="size-3.5" />
                {t('knowledge.entries.tab')}
              </TabsTrigger>
            )}
            <TabsTrigger value="retrieve" className="gap-1.5">
              <Search className="size-3.5" />
              {t('knowledge.retrieve')}
            </TabsTrigger>
          </TabsList>

          {/* 元数据 */}
          <TabsContent
            value="metadata"
            className="flex-1 min-h-0 overflow-y-auto mt-4"
          >
            <div className="mx-auto max-w-3xl space-y-6 pb-8">
              <KBForm
                initKbId={id}
                onNewKbCreated={handleNewKbCreated}
                onKbUpdated={handleKbUpdated}
                onDirtyChange={setFormDirty}
              />

              {/* 危险操作区 */}
              <Card className="border-destructive/50">
                <CardHeader>
                  <CardTitle className="text-destructive">
                    {t('knowledge.dangerZone')}
                  </CardTitle>
                  <CardDescription>
                    {t('knowledge.dangerZoneDescription')}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <p className="text-sm font-medium">
                        {t('knowledge.deleteKbAction')}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {t('knowledge.deleteKbHint')}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      onClick={() => setShowDeleteConfirm(true)}
                    >
                      <Trash2 className="size-4 mr-1.5" />
                      {t('common.delete')}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* 文档 */}
          {hasDocumentCapability() && (
            <TabsContent
              value="documents"
              className="flex-1 min-h-0 overflow-y-auto mt-4"
            >
              <KBDoc
                kbId={id}
                knowledgeEnginePluginId={kbInfo?.knowledge_engine?.plugin_id}
                ragEngineName={kbInfo?.knowledge_engine?.name}
                ragEngineCapabilities={kbInfo?.knowledge_engine?.capabilities}
              />
            </TabsContent>
          )}

          {isLocalFaqKnowledgeBase() && (
            <TabsContent
              value="entries"
              className="flex-1 min-h-0 overflow-y-auto mt-4"
            >
              <KBEntries kbId={id} />
            </TabsContent>
          )}

          {/* 检索 */}
          <TabsContent
            value="retrieve"
            className="flex-1 min-h-0 overflow-y-auto mt-4"
          >
            <KBRetrieveGeneric
              kbId={id}
              retrieveFunction={retrieveFunction}
              getResultTitle={getRetrieveResultTitle}
            />
          </TabsContent>
        </Tabs>
      </div>

      {/* 删除确认弹窗 */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
            <DialogDescription className="sr-only">
              {t('knowledge.deleteKnowledgeBaseConfirmation')}
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            {t('knowledge.deleteKnowledgeBaseConfirmation')}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteConfirm(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              {t('common.confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
