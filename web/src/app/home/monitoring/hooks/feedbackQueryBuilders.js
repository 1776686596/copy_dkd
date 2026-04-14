function appendBaseFeedbackParams(queryParams, params) {
  params.botIds?.forEach((id) => queryParams.append('botId', id));
  params.pipelineIds?.forEach((id) => queryParams.append('pipelineId', id));

  if (params.startTime) {
    queryParams.append('startTime', params.startTime);
  }

  if (params.endTime) {
    queryParams.append('endTime', params.endTime);
  }
}

export function buildFeedbackStatsQuery(params = {}) {
  const queryParams = new URLSearchParams();
  appendBaseFeedbackParams(queryParams, params);
  return queryParams.toString();
}

export function buildFeedbackListQuery(params = {}) {
  const queryParams = new URLSearchParams();
  appendBaseFeedbackParams(queryParams, params);

  if (params.feedbackType) {
    queryParams.append(
      'feedbackType',
      params.feedbackType === 'like' ? '1' : '2',
    );
  }

  if (params.limit) {
    queryParams.append('limit', params.limit.toString());
  }

  if (params.offset) {
    queryParams.append('offset', params.offset.toString());
  }

  return queryParams.toString();
}
