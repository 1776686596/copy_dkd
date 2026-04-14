import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { httpClient } from '@/app/infra/http/HttpClient';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { ParserInfo } from '@/app/infra/entities/api';
import { CustomApiError, I18nObject } from '@/app/infra/entities/common';
import { extractI18nObject } from '@/i18n/I18nProvider';

interface FileUploadZoneProps {
  kbId: string;
  knowledgeEnginePluginId?: string | null;
  ragEngineName?: I18nObject;
  ragEngineCapabilities?: string[];
  onUploadSuccess: () => void;
  onUploadError: (error: string) => void;
}

export default function FileUploadZone({
  kbId,
  knowledgeEnginePluginId,
  ragEngineName,
  ragEngineCapabilities,
  onUploadSuccess,
  onUploadError,
}: FileUploadZoneProps) {
  const { t } = useTranslation();
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  // 解析器选择状态
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [availableParsers, setAvailableParsers] = useState<ParserInfo[]>([]);
  const [selectedParser, setSelectedParser] = useState<string>('builtin');
  const [loadingParsers, setLoadingParsers] = useState(false);

  // 知识引擎是否原生支持文档解析。
  // 这里先按引擎能力做粗粒度判断，避免为了演示改动更多链路。
  const ragEngineCanParse =
    ragEngineCapabilities?.includes('doc_parsing') ?? false;
  const isLocalFaqEngine = knowledgeEnginePluginId === 'builtin/local-faq';

  // 选择文件后，查询可用解析器
  useEffect(() => {
    if (!pendingFile) return;

    if (isLocalFaqEngine) {
      setAvailableParsers([]);
      setSelectedParser('builtin');
      setLoadingParsers(false);
      return;
    }

    const mimeType = pendingFile.type || undefined;
    setLoadingParsers(true);
    httpClient
      .listParsers(mimeType)
      .then((resp) => {
        const parsers = resp.parsers || [];
        setAvailableParsers(parsers);
        if (ragEngineCanParse) {
          setSelectedParser('builtin');
        } else if (parsers.length > 0) {
          setSelectedParser(parsers[0].plugin_id);
        } else {
          setSelectedParser('');
        }
      })
      .catch(() => {
        setAvailableParsers([]);
      })
      .finally(() => {
        setLoadingParsers(false);
      });
  }, [isLocalFaqEngine, pendingFile, ragEngineCanParse]);

  const doUpload = useCallback(
    async (file: File, parserPluginId?: string) => {
      setIsUploading(true);
      const toastId = toast.loading(t('knowledge.documentsTab.uploadingFile'));

      try {
        // 1. 先上传原始文件
        const uploadResult = await httpClient.uploadDocumentFile(file);

        // 2. 再把文件挂到知识库上，可选指定解析器
        await httpClient.uploadKnowledgeBaseFile(
          kbId,
          uploadResult.file_id,
          parserPluginId,
        );

        toast.success(t('knowledge.documentsTab.uploadSuccess'), {
          id: toastId,
        });
        onUploadSuccess();
      } catch (error) {
        console.error('File upload failed:', error);
        const errorMessage =
          t('knowledge.documentsTab.uploadError') +
          (error as CustomApiError).msg;
        toast.error(errorMessage, { id: toastId });
        onUploadError(errorMessage);
      } finally {
        setIsUploading(false);
        setPendingFile(null);
        setAvailableParsers([]);
        setSelectedParser('builtin');
      }
    },
    [kbId, onUploadSuccess, onUploadError, t],
  );

  const handleFileSelected = useCallback(
    async (file: File) => {
      if (isUploading) return;

      // 文件大小限制 10MB
      const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
      if (file.size > MAX_FILE_SIZE) {
        toast.error(t('knowledge.documentsTab.fileSizeExceeded'));
        return;
      }

      // 先置为加载中，避免自动上传逻辑早于解析器查询结果触发。
      setLoadingParsers(true);
      setPendingFile(file);
    },
    [isUploading, t],
  );

  // 若引擎可直接解析且无需额外解析器，则自动上传
  useEffect(() => {
    if (
      pendingFile &&
      !loadingParsers &&
      ragEngineCanParse &&
      availableParsers.length === 0
    ) {
      doUpload(pendingFile);
    }
  }, [
    pendingFile,
    loadingParsers,
    ragEngineCanParse,
    availableParsers,
    doUpload,
  ]);

  const handleConfirmUpload = useCallback(() => {
    if (!pendingFile) return;
    const parserPluginId =
      selectedParser === 'builtin' ? undefined : selectedParser;
    doUpload(pendingFile, parserPluginId);
  }, [pendingFile, selectedParser, doUpload]);

  const handleCancelUpload = useCallback(() => {
    setPendingFile(null);
    setAvailableParsers([]);
    setSelectedParser('builtin');
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);

      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) {
        handleFileSelected(files[0]);
      }
    },
    [handleFileSelected],
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        handleFileSelected(files[0]);
      }
      // 重置 input，允许再次选择同一个文件
      e.target.value = '';
    },
    [handleFileSelected],
  );

  // 需要用户选择解析器，或当前没有可用解析器时，显示选择区
  const showParserSelector =
    pendingFile &&
    !loadingParsers &&
    !isLocalFaqEngine &&
    (availableParsers.length > 0 || !ragEngineCanParse);

  const noParserAvailable = !ragEngineCanParse && availableParsers.length === 0;

  return (
    <Card className="mb-4">
      <CardContent className="p-4">
        {showParserSelector ? (
          <div className="space-y-3">
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
              {pendingFile.name}
            </p>
            {noParserAvailable ? (
              <div className="rounded-md bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 p-3">
                <p className="text-sm text-yellow-800 dark:text-yellow-200">
                  {t('knowledge.documentsTab.noParserAvailable')}
                </p>
                <Link
                  to="/home/market?category=Parser"
                  className="text-sm text-primary hover:underline mt-1 inline-block"
                >
                  {t('knowledge.documentsTab.installParserHint')}
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                <label className="text-sm text-gray-600 dark:text-gray-400">
                  {t('knowledge.documentsTab.selectParser')}
                </label>
                <Select
                  value={selectedParser}
                  onValueChange={setSelectedParser}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ragEngineCanParse && (
                      <SelectItem value="builtin">
                        {ragEngineName
                          ? extractI18nObject(ragEngineName)
                          : t('knowledge.documentsTab.builtInParser')}
                      </SelectItem>
                    )}
                    {availableParsers.map((parser) => (
                      <SelectItem
                        key={parser.plugin_id}
                        value={parser.plugin_id}
                      >
                        {extractI18nObject(parser.name)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={handleCancelUpload}>
                {t('knowledge.documentsTab.cancelUpload')}
              </Button>
              {!noParserAvailable && (
                <Button size="sm" onClick={handleConfirmUpload}>
                  {t('knowledge.documentsTab.confirmUpload')}
                </Button>
              )}
            </div>
          </div>
        ) : (
          <div
            className={`
              relative border-2 border-dashed rounded-lg p-4 text-center transition-colors
              ${
                isDragOver
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-300 hover:border-gray-400'
              }
              ${isUploading || loadingParsers ? 'opacity-50 pointer-events-none' : ''}
            `}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <input
              type="file"
              id="file-upload"
              className="hidden"
              onChange={handleFileSelect}
              accept={
                isLocalFaqEngine
                  ? '.xlsx,.csv,.json'
                  : '.pdf,.doc,.docx,.txt,.md,.html,.zip'
              }
              disabled={isUploading || loadingParsers}
            />

            <label htmlFor="file-upload" className="cursor-pointer block">
              <div className="space-y-2">
                <div className="mx-auto w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center">
                  <svg
                    className="w-5 h-5 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                    />
                  </svg>
                </div>

                <div>
                  <p className="text-base font-medium text-gray-900 dark:text-gray-100">
                    {isUploading
                      ? t('knowledge.documentsTab.uploading')
                      : t('knowledge.documentsTab.dragAndDrop')}
                  </p>
                  <p className="text-xs text-gray-500 mt-1 dark:text-gray-400">
                    {isLocalFaqEngine
                      ? t('knowledge.documentsTab.supportedFormatsLocalFaq')
                      : t('knowledge.documentsTab.supportedFormats')}
                  </p>
                </div>
              </div>
            </label>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
