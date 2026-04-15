from __future__ import annotations

from unittest.mock import Mock

def test_resolve_knowledge_base_uuids_uses_same_name_knowledge_base_when_binding_is_empty():
    from langbot.pkg.pipeline.preproc.knowledge_base_selection import resolve_knowledge_base_uuids

    runtime_kb = Mock()
    runtime_kb.get_name = Mock(return_value='聚玩测试')
    runtime_kb.get_uuid = Mock(return_value='kb-auto-match')
    runtime_knowledge_bases = {
        'kb-auto-match': runtime_kb,
    }

    kb_uuids = resolve_knowledge_base_uuids(
        local_agent_config={'knowledge-bases': []},
        query_variables={'_monitoring_pipeline_name': '聚玩测试'},
        runtime_knowledge_bases=runtime_knowledge_bases,
    )

    assert kb_uuids == ['kb-auto-match']
