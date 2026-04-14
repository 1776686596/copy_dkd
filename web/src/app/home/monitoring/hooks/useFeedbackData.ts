import { useState, useEffect, useCallback } from 'react';
import { httpClient } from '@/app/infra/http';
import { FeedbackRecord, FeedbackStats } from '../types/monitoring';
import { parseUTCTimestamp } from '../utils/dateUtils';
import {
  buildFeedbackListQuery,
  buildFeedbackStatsQuery,
} from './feedbackQueryBuilders.js';
import type { UseFeedbackDataParams } from './feedbackQueryBuilders';

interface RawFeedbackRecord {
  id: string;
  timestamp: string;
  feedback_id: string;
  feedback_type: number;
  feedback_content?: string;
  inaccurate_reasons?: string;
  bot_id?: string;
  bot_name?: string;
  pipeline_id?: string;
  pipeline_name?: string;
  session_id?: string;
  message_id?: string;
  stream_id?: string;
  user_id?: string;
  platform?: string;
}

interface RawFeedbackStats {
  total_feedback: number;
  total_likes: number;
  total_dislikes: number;
  satisfaction_rate: number;
  by_bot?: Array<{
    bot_id: string;
    bot_name: string;
    total: number;
    likes: number;
    dislikes: number;
  }>;
}

/**
 * Custom hook for fetching and managing feedback data
 */
export function useFeedbackData(params: UseFeedbackDataParams = {}) {
  const [feedback, setFeedback] = useState<FeedbackRecord[]>([]);
  const [stats, setStats] = useState<FeedbackStats | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const statsQuery = buildFeedbackStatsQuery(params);
  const feedbackQuery = buildFeedbackListQuery(params);

  const fetchStats = useCallback(async () => {
    try {
      const result = await httpClient.get<RawFeedbackStats>(
        `/api/v1/monitoring/feedback/stats?${statsQuery}`,
      );

      if (result) {
        setStats({
          totalFeedback: result.total_feedback,
          totalLikes: result.total_likes,
          totalDislikes: result.total_dislikes,
          satisfactionRate: result.satisfaction_rate,
          byBot: result.by_bot?.map((bot) => ({
            botId: bot.bot_id,
            botName: bot.bot_name,
            totalFeedback: bot.total,
            totalLikes: bot.likes,
            totalDislikes: bot.dislikes,
            satisfactionRate:
              bot.total > 0 ? Math.round((bot.likes / bot.total) * 100) : 0,
          })),
        });
      }
    } catch (err) {
      console.error('Failed to fetch feedback stats:', err);
    }
  }, [statsQuery]);

  const fetchFeedback = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await httpClient.get<{
        feedback: RawFeedbackRecord[];
        total: number;
      }>(`/api/v1/monitoring/feedback?${feedbackQuery}`);

      if (result) {
        const transformedFeedback: FeedbackRecord[] = result.feedback.map(
          (item) => ({
            id: item.id,
            timestamp: parseUTCTimestamp(item.timestamp),
            feedbackId: item.feedback_id,
            feedbackType: item.feedback_type === 1 ? 'like' : 'dislike',
            feedbackContent: item.feedback_content,
            inaccurateReasons: item.inaccurate_reasons
              ? JSON.parse(item.inaccurate_reasons)
              : undefined,
            botId: item.bot_id,
            botName: item.bot_name,
            pipelineId: item.pipeline_id,
            pipelineName: item.pipeline_name,
            sessionId: item.session_id,
            messageId: item.message_id,
            streamId: item.stream_id,
            userId: item.user_id,
            platform: item.platform,
          }),
        );

        setFeedback(transformedFeedback);
        setTotal(result.total);
      }
    } catch (err) {
      setError(err as Error);
      console.error('Failed to fetch feedback:', err);
    } finally {
      setLoading(false);
    }
  }, [feedbackQuery]);

  const refetch = useCallback(() => {
    void fetchStats();
    void fetchFeedback();
  }, [fetchStats, fetchFeedback]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return {
    feedback,
    stats,
    total,
    loading,
    error,
    refetch,
  };
}
