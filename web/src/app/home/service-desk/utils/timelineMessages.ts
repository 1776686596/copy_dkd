import type { ServiceDeskTimelineMessage } from '@/app/infra/entities/api';

export declare function mergeServiceDeskTimelineMessages(
  detailMessages?: ServiceDeskTimelineMessage[] | null,
  monitoringMessages?: ServiceDeskTimelineMessage[] | null,
): ServiceDeskTimelineMessage[];
