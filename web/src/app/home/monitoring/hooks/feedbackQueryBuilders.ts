export interface UseFeedbackDataParams {
  botIds?: string[];
  pipelineIds?: string[];
  startTime?: string;
  endTime?: string;
  feedbackType?: 'like' | 'dislike';
  limit?: number;
  offset?: number;
}

export declare function buildFeedbackStatsQuery(
  params?: UseFeedbackDataParams,
): string;

export declare function buildFeedbackListQuery(
  params?: UseFeedbackDataParams,
): string;
