import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { KnowledgeBaseEntry } from '@/app/infra/entities/api';

export interface KBEntryFormValue {
  questions: string[];
  answer: string;
  enabled: boolean;
}

interface KBEntryDialogProps {
  open: boolean;
  entry?: KnowledgeBaseEntry | null;
  saving: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (value: KBEntryFormValue) => Promise<void> | void;
}

function questionsToText(entry?: KnowledgeBaseEntry | null): string {
  return entry?.questions?.join('\n') ?? '';
}

export default function KBEntryDialog({
  open,
  entry,
  saving,
  onOpenChange,
  onSubmit,
}: KBEntryDialogProps) {
  const { t } = useTranslation();
  const [questionsText, setQuestionsText] = useState('');
  const [answer, setAnswer] = useState('');
  const [enabled, setEnabled] = useState(true);

  useEffect(() => {
    if (!open) return;
    setQuestionsText(questionsToText(entry));
    setAnswer(entry?.answer ?? '');
    setEnabled(entry?.enabled ?? true);
  }, [entry, open]);

  const parsedQuestions = useMemo(
    () =>
      questionsText
        .split(/[\n；;]+/)
        .map((item) => item.trim())
        .filter(Boolean),
    [questionsText],
  );

  const isValid = parsedQuestions.length > 0 && answer.trim().length > 0;

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isValid || saving) return;
    await onSubmit({
      questions: parsedQuestions,
      answer: answer.trim(),
      enabled,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {entry ? t('knowledge.entries.editTitle') : t('knowledge.entries.addTitle')}
          </DialogTitle>
          <DialogDescription>
            {t('knowledge.entries.dialogDescription')}
          </DialogDescription>
        </DialogHeader>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <Label htmlFor="kb-entry-questions">
              {t('knowledge.entries.questions')}
            </Label>
            <Textarea
              id="kb-entry-questions"
              rows={5}
              value={questionsText}
              onChange={(event) => setQuestionsText(event.target.value)}
              placeholder={t('knowledge.entries.questionsPlaceholder')}
            />
            <p className="text-xs text-muted-foreground">
              {t('knowledge.entries.questionsHint')}
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="kb-entry-answer">
              {t('knowledge.entries.answer')}
            </Label>
            <Textarea
              id="kb-entry-answer"
              rows={8}
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
              placeholder={t('knowledge.entries.answerPlaceholder')}
            />
          </div>

          {entry?.source_file_id && (
            <div className="space-y-2">
              <Label htmlFor="kb-entry-source">
                {t('knowledge.entries.sourceFile')}
              </Label>
              <Input
                id="kb-entry-source"
                value={entry.source_file_id}
                readOnly
                disabled
              />
            </div>
          )}

          <div className="flex items-center justify-between rounded-lg border px-4 py-3">
            <div className="space-y-1">
              <Label htmlFor="kb-entry-enabled">
                {t('knowledge.entries.enabled')}
              </Label>
              <p className="text-xs text-muted-foreground">
                {t('knowledge.entries.enabledHint')}
              </p>
            </div>
            <Switch
              id="kb-entry-enabled"
              checked={enabled}
              onCheckedChange={setEnabled}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={!isValid || saving}>
              {saving ? t('common.saving') : t('common.save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
