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

interface SessionFiltersProps {
  queueFilters: ServiceDeskQueueStatus[];
  queueFilter: ServiceDeskQueueStatus;
  searchKeyword: string;
  claimedByFilter: string;
  loading: boolean;
  onQueueFilterChange: (value: ServiceDeskQueueStatus) => void;
  onSearchKeywordChange: (value: string) => void;
  onClaimedByFilterChange: (value: string) => void;
  onRefresh: () => void;
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
}: SessionFiltersProps) {
  const { t } = useTranslation();

  return (
    <Card className="gap-4 py-4">
      <CardContent className="flex flex-col gap-4 px-4">
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
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onRefresh}
            >
              <RefreshCw className={loading ? 'animate-spin' : undefined} />
              {t('serviceDesk.workbench.refresh')}
            </Button>
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_220px]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchKeyword}
              onChange={(event) => onSearchKeywordChange(event.target.value)}
              placeholder={t('serviceDesk.workbench.searchPlaceholder')}
              className="pl-9"
            />
          </div>
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
        </div>
      </CardContent>
    </Card>
  );
}
