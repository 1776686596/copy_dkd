import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useTranslation } from 'react-i18next';
import { RetrieveResult } from '@/app/infra/entities/api';
import { CustomApiError } from '@/app/infra/entities/common';
import { toast } from 'sonner';

interface KBRetrieveGenericProps {
  kbId: string;
  retrieveFunction: (
    kbId: string,
    query: string,
  ) => Promise<{ results: RetrieveResult[] }>;
  getResultTitle?: (result: RetrieveResult) => string;
}

/**
 * 通用知识库检索组件，同时兼容内置和插件型知识库。
 */
export default function KBRetrieveGeneric({
  kbId,
  retrieveFunction,
  getResultTitle,
}: KBRetrieveGenericProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<RetrieveResult[]>([]);
  const [loading, setLoading] = useState(false);

  const handleRetrieve = async () => {
    if (!query.trim()) return;

    setLoading(true);
    try {
      setResults([]);
      const response = await retrieveFunction(kbId, query);
      setResults(response.results);
    } catch (error) {
      console.error('Retrieve failed:', error);
      toast.error(t('knowledge.retrieveError') + (error as CustomApiError).msg);
    } finally {
      setLoading(false);
    }
  };

  const getTitle = (result: RetrieveResult): string => {
    if (getResultTitle) {
      return getResultTitle(result);
    }
    // 默认优先展示文档名，其次回退到 file_id 或结果 id
    return (
      (result.metadata.document_name as string) ||
      (result.metadata.file_id as string) ||
      result.id
    );
  };

  /**
   * 从 content 数组中提取文本内容。
   */
  const extractTextFromContent = (result: RetrieveResult): string => {
    // 优先读取结构化 content 中的文本片段
    if (result.content && Array.isArray(result.content)) {
      const textParts = result.content
        .filter((item) => item.type === 'text' && item.text)
        .map((item) => item.text);

      if (textParts.length > 0) {
        return textParts.join('\n\n');
      }
    }

    return '';
  };

  const renderResultBody = (result: RetrieveResult) => {
    const standardAnswer = result.metadata.local_faq_answer as string | undefined;
    const finalAnswer =
      (result.metadata.final_answer as string | undefined) ||
      extractTextFromContent(result);

    if (standardAnswer) {
      const showFinalAnswer = finalAnswer && finalAnswer !== standardAnswer;

      return (
        <div className="space-y-3 text-sm">
          <div className="space-y-1">
            <div className="text-xs font-medium text-muted-foreground">
              {t('knowledge.entries.standardAnswer')}
            </div>
            <p className="whitespace-pre-wrap">{standardAnswer}</p>
          </div>

          {showFinalAnswer && (
            <div className="space-y-1">
              <div className="text-xs font-medium text-muted-foreground">
                {t('knowledge.entries.finalAnswer')}
              </div>
              <p className="whitespace-pre-wrap">{finalAnswer}</p>
            </div>
          )}
        </div>
      );
    }

    return (
      <p className="text-sm whitespace-pre-wrap">{extractTextFromContent(result)}</p>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('knowledge.queryPlaceholder')}
          onKeyPress={(e) => e.key === 'Enter' && handleRetrieve()}
        />
        <Button onClick={handleRetrieve} disabled={loading || !query.trim()}>
          {t('knowledge.query')}
        </Button>
      </div>

      <div className="space-y-3">
        {results.length === 0 && !loading && (
          <p className="text-muted-foreground">{t('knowledge.noResults')}</p>
        )}

        {loading ? (
          <p className="text-muted-foreground">{t('common.loading')}</p>
        ) : (
          results.map((result) => (
            <Card key={result.id} className="w-full">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium flex justify-between items-center gap-3">
                  <div className="flex flex-col gap-2">
                    <span>{getTitle(result)}</span>
                    {result.metadata.matched_question && (
                      <Badge variant="secondary" className="w-fit">
                        {t('knowledge.entries.matchedQuestion')}:
                        {' ' + String(result.metadata.matched_question)}
                      </Badge>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground shrink-0">
                    {t('knowledge.distance')}:{' '}
                    {(result.distance ?? 0).toFixed(4)}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>{renderResultBody(result)}</CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
