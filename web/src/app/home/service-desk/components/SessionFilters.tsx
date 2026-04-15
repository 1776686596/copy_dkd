import { useTranslation } from 'react-i18next';
import { RefreshCw, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ServiceDeskQueueStatus } from '@/app/infra/entities/api';
import { cn } from '@/lib/utils';

type ServiceDeskQueueFilter = ServiceDeskQueueStatus | 'all';

interface SessionFiltersProps {
  queueFilters: ServiceDeskQueueFilter[];
  queueFilter: ServiceDeskQueueFilter;
  searchKeyword: string;
  claimedByFilter: string;
  loading: boolean;
  onQueueFilterChange: (value: ServiceDeskQueueFilter) => void;
  onSearchKeywordChange: (value: string) => void;
  onClaimedByFilterChange: (value: string) => void;
  onRefresh: () => void;
  compact?: boolean;
  className?: string;
  hideClaimedByFilter?: boolean;
}

export default function SessionFilters({
  queueFilters,
  queueFilter,
  searchKeyword,
  claimedByFilter,
  loading,
  onQueueFilterChange,
  onSearchKeywordChange,
  onClaimedByFilterChange,
  onRefresh,
  compact = false,
  className,
  hideClaimedByFilter = false,
}: SessionFiltersProps) {
  const { t } = useTranslation();

  const content = (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="space-y-1">
          <div className="text-sm font-medium">
            {t('serviceDesk.workbench.queueFilter')}
          </div>
          <div className="text-xs text-muted-foreground">
            {t('serviceDesk.workbench.autoRefresh')}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {queueFilters.map((filter) => (
            <Button
              key={filter}
              type="button"
              variant={queueFilter === filter ? 'default' : 'outline'}
              size="sm"
              onClick={() => onQueueFilterChange(filter)}
            >
              {t(`serviceDesk.queueStatus.${filter}`)}
            </Button>
          ))}
          <Button type="button" variant="outline" size="sm" onClick={onRefresh}>
            <RefreshCw className={loading ? 'animate-spin' : undefined} />
            {t('serviceDesk.workbench.refresh')}
          </Button>
        </div>
      </div>

      <div
        className={cn(
          'grid gap-3',
          hideClaimedByFilter ? 'grid-cols-1' : 'lg:grid-cols-[minmax(0,1fr)_220px]',
        )}
      >
        <div className="relative">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchKeyword}
            onChange={(event) => onSearchKeywordChange(event.target.value)}
            placeholder={t('serviceDesk.workbench.searchPlaceholder')}
            className="pl-9"
          />
        </div>
        {hideClaimedByFilter ? null : (
          <Select
            value={claimedByFilter}
            onValueChange={onClaimedByFilterChange}
          >
            <SelectTrigger>
              <SelectValue
                placeholder={t('serviceDesk.workbench.claimedByFilter')}
              />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">
                {t('serviceDesk.workbench.claimedByAll')}
              </SelectItem>
              <SelectItem value="claimed">
                {t('serviceDesk.workbench.claimedByClaimed')}
              </SelectItem>
              <SelectItem value="unclaimed">
                {t('serviceDesk.workbench.claimedByUnclaimed')}
              </SelectItem>
            </SelectContent>
          </Select>
        )}
      </div>
    </div>
  );

  if (compact) {
    return (
      <div
        className={cn(
          'rounded-[24px] border border-border/70 bg-background/96 p-4 shadow-sm backdrop-blur',
          className,
        )}
      >
        {content}
      </div>
    );
  }

  return (
    <Card className={cn('gap-4 py-4', className)}>
      <CardContent className="px-4">{content}</CardContent>
    </Card>
  );
}
