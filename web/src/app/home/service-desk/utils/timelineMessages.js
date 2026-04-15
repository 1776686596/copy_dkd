function buildMessageKey(message) {
  if (message?.id) {
    return message.id;
  }

  return [
    message?.session_id ?? '',
    message?.timestamp ?? '',
    message?.role ?? '',
    message?.message_content ?? '',
  ].join('::');
}

export function mergeServiceDeskTimelineMessages(
  detailMessages = [],
  monitoringMessages = [],
) {
  const merged = new Map();

  [...detailMessages, ...monitoringMessages].forEach((message) => {
    if (!message) return;
    const key = buildMessageKey(message);
    if (!merged.has(key)) {
      merged.set(key, message);
    }
  });

  return Array.from(merged.values());
}
