from __future__ import annotations

from collections.abc import Mapping


def resolve_knowledge_base_uuids(
    local_agent_config: dict,
    query_variables: Mapping[str, object] | None,
    runtime_knowledge_bases: Mapping[str, object] | None,
) -> list[str]:
    kb_uuids = list(local_agent_config.get('knowledge-bases', []) or [])
    if kb_uuids:
        return kb_uuids

    old_kb_uuid = str(local_agent_config.get('knowledge-base', '') or '').strip()
    if old_kb_uuid and old_kb_uuid != '__none__':
        return [old_kb_uuid]

    pipeline_name = str((query_variables or {}).get('_monitoring_pipeline_name', '') or '').strip()
    if not pipeline_name or not runtime_knowledge_bases:
        return []

    matched_uuids: list[str] = []
    for kb_uuid, runtime_kb in runtime_knowledge_bases.items():
        kb_name_getter = getattr(runtime_kb, 'get_name', None)
        if not callable(kb_name_getter):
            continue

        kb_name = str(kb_name_getter() or '').strip()
        if kb_name != pipeline_name:
            continue

        kb_uuid_getter = getattr(runtime_kb, 'get_uuid', None)
        resolved_kb_uuid = kb_uuid_getter() if callable(kb_uuid_getter) else kb_uuid
        resolved_kb_uuid = str(resolved_kb_uuid or '').strip()
        if resolved_kb_uuid:
            matched_uuids.append(resolved_kb_uuid)

    if len(matched_uuids) == 1:
        return matched_uuids

    return []
