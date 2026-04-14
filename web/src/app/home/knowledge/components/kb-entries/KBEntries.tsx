import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { CustomApiError } from '@/app/infra/entities/common';
import { KnowledgeBaseEntry } from '@/app/infra/entities/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import KBEntryDialog, { KBEntryFormValue } from './KBEntryDialog';

export default function KBEntries({ kbId }: { kbId: string }) {
  const { t } = useTranslation();
  const [entries, setEntries] = useState<KnowledgeBaseEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingEntry, setEditingEntry] = useState<KnowledgeBaseEntry | null>(
    null,
  );

  const sortedEntries = useMemo(
    () =>
      [...entries].sort((left, right) => {
        if (left.sort_order !== right.sort_order) {
          return left.sort_order - right.sort_order;
        }
        return left.uuid.localeCompare(right.uuid);
      }),
    [entries],
  );

  const loadEntries = useCallback(async () => {
    setLoading(true);
    try {
      const response = await httpClient.getKnowledgeBaseEntries(kbId);
      setEntries(response.entries);
    } catch (error) {
      console.error('Failed to load knowledge base entries:', error);
      toast.error(
        t('knowledge.entries.loadError') + (error as CustomApiError).msg,
      );
    } finally {
      setLoading(false);
    }
  }, [kbId, t]);

  useEffect(() => {
    void loadEntries();
  }, [loadEntries]);

  const handleCreate = () => {
    setEditingEntry(null);
    setDialogOpen(true);
  };

  const handleEdit = (entry: KnowledgeBaseEntry) => {
    setEditingEntry(entry);
    setDialogOpen(true);
  };

  const handleDelete = async (entry: KnowledgeBaseEntry) => {
    if (!window.confirm(t('knowledge.entries.deleteConfirm'))) {
      return;
    }

    try {
      await httpClient.deleteKnowledgeBaseEntry(kbId, entry.uuid);
      toast.success(t('knowledge.entries.deleteSuccess'));
      await loadEntries();
    } catch (error) {
      console.error('Failed to delete knowledge base entry:', error);
      toast.error(
        t('knowledge.entries.deleteError') + (error as CustomApiError).msg,
      );
    }
  };

  const handleSubmit = async (value: KBEntryFormValue) => {
    setSaving(true);
    try {
      if (editingEntry) {
        await httpClient.updateKnowledgeBaseEntry(kbId, editingEntry.uuid, {
          ...value,
          sort_order: editingEntry.sort_order,
        });
        toast.success(t('knowledge.entries.updateSuccess'));
      } else {
        await httpClient.createKnowledgeBaseEntry(kbId, value);
        toast.success(t('knowledge.entries.createSuccess'));
      }

      setDialogOpen(false);
      setEditingEntry(null);
      await loadEntries();
    } catch (error) {
      console.error('Failed to save knowledge base entry:', error);
      toast.error(
        t('knowledge.entries.saveError') + (error as CustomApiError).msg,
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div className="space-y-1">
            <CardTitle>{t('knowledge.entries.title')}</CardTitle>
            <CardDescription>
              {t('knowledge.entries.description')}
            </CardDescription>
          </div>
          <Button onClick={handleCreate}>
            <Plus className="mr-1.5 size-4" />
            {t('knowledge.entries.addAction')}
          </Button>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">{t('common.loading')}</p>
          ) : sortedEntries.length === 0 ? (
            <div className="rounded-lg border border-dashed px-4 py-10 text-center text-sm text-muted-foreground">
              {t('knowledge.entries.empty')}
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('knowledge.entries.questions')}</TableHead>
                    <TableHead>{t('knowledge.entries.answer')}</TableHead>
                    <TableHead>{t('knowledge.entries.status')}</TableHead>
                    <TableHead>{t('knowledge.entries.sourceFile')}</TableHead>
                    <TableHead className="w-[120px] text-right">
                      {t('common.actions')}
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedEntries.map((entry) => (
                    <TableRow key={entry.uuid}>
                      <TableCell className="align-top">
                        <div className="space-y-1">
                          {entry.questions.map((question) => (
                            <div key={question} className="text-sm">
                              {question}
                            </div>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="max-w-[420px] align-top">
                        <div className="text-sm whitespace-pre-wrap line-clamp-4">
                          {entry.answer}
                        </div>
                      </TableCell>
                      <TableCell className="align-top">
                        <Badge variant={entry.enabled ? 'default' : 'secondary'}>
                          {entry.enabled
                            ? t('knowledge.entries.enabled')
                            : t('knowledge.entries.disabled')}
                        </Badge>
                      </TableCell>
                      <TableCell className="align-top text-xs text-muted-foreground">
                        {entry.source_file_id || t('common.none')}
                      </TableCell>
                      <TableCell className="align-top">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => handleEdit(entry)}
                          >
                            <Pencil className="size-4" />
                          </Button>
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => void handleDelete(entry)}
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <KBEntryDialog
        open={dialogOpen}
        entry={editingEntry}
        saving={saving}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) {
            setEditingEntry(null);
          }
        }}
        onSubmit={handleSubmit}
      />
    </>
  );
}
