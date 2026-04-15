from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


def _write_local_faq(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding='utf-8')


def test_load_local_faq_entries_reads_valid_json(tmp_path):
    faq_path = tmp_path / 'local-faq.json'
    _write_local_faq(
        faq_path,
        [
            {
                'questions': ['哪个职业好玩？', '职业推荐'],
                'answer': '鬼王前期开荒更快，焚天更适合中后期团战。',
            }
        ],
    )

    local_faq = import_module('langbot.pkg.utils.local_faq')
    entries = local_faq.load_local_faq_entries(str(faq_path))

    assert len(entries) == 1
    assert entries[0].questions == ['哪个职业好玩？', '职业推荐']
    assert entries[0].answer == '鬼王前期开荒更快，焚天更适合中后期团战。'


def test_match_local_faq_entry_prefers_normalized_exact_match(tmp_path):
    faq_path = tmp_path / 'local-faq.json'
    _write_local_faq(
        faq_path,
        [
            {
                'questions': ['哪个职业好玩？'],
                'answer': '鬼王前期开荒更快，焚天更适合中后期团战。',
            },
            {
                'questions': ['有什么福利/内部号'],
                'answer': '下载注册后把区服和角色名给我，我给你安排礼包和 CDK。',
            },
        ],
    )

    local_faq = import_module('langbot.pkg.utils.local_faq')
    entries = local_faq.load_local_faq_entries(str(faq_path))
    matched = local_faq.match_local_faq_entry(entries, '哪个职业好玩', min_similarity=0.95)

    assert matched is not None
    assert matched.answer == '鬼王前期开荒更快，焚天更适合中后期团战。'


def test_match_local_faq_entry_returns_none_when_below_threshold(tmp_path):
    faq_path = tmp_path / 'local-faq.json'
    _write_local_faq(
        faq_path,
        [
            {
                'questions': ['哪个职业好玩？'],
                'answer': '鬼王前期开荒更快，焚天更适合中后期团战。',
            }
        ],
    )

    local_faq = import_module('langbot.pkg.utils.local_faq')
    entries = local_faq.load_local_faq_entries(str(faq_path))
    matched = local_faq.match_local_faq_entry(entries, '今天天气怎么样', min_similarity=0.98)

    assert matched is None


@pytest.mark.asyncio
async def test_polish_local_faq_answer_returns_model_reply_when_close():
    import langbot_plugin.api.entities.builtin.provider.message as provider_message

    from langbot.pkg.provider.runners.localagent import LocalAgentRunner

    mock_app = Mock()
    mock_app.logger = Mock()
    runner = LocalAgentRunner(mock_app, pipeline_config={})

    mock_model = Mock()
    runner._get_model_candidates = AsyncMock(return_value=[mock_model])
    runner._invoke_with_fallback = AsyncMock(
        return_value=(
            provider_message.Message(
                role='assistant',
                content='更推荐鬼王，前期开荒更快，焚天更适合中后期团战。',
            ),
            mock_model,
        )
    )

    query = Mock()
    query.pipeline_config = {'output': {'misc': {'remove-think': False}}}

    result = await runner._polish_local_faq_answer(
        query=query,
        user_message_text='哪个职业好玩',
        matched_question='哪个职业好玩？',
        standard_answer='鬼王前期开荒更快，焚天更适合中后期团战。',
    )

    assert result == '更推荐鬼王，前期开荒更快，焚天更适合中后期团战。'


@pytest.mark.asyncio
async def test_polish_local_faq_answer_falls_back_when_model_reply_is_off_topic():
    import langbot_plugin.api.entities.builtin.provider.message as provider_message

    from langbot.pkg.provider.runners.localagent import LocalAgentRunner

    mock_app = Mock()
    mock_app.logger = Mock()
    runner = LocalAgentRunner(mock_app, pipeline_config={})

    mock_model = Mock()
    runner._get_model_candidates = AsyncMock(return_value=[mock_model])
    runner._invoke_with_fallback = AsyncMock(
        return_value=(provider_message.Message(role='assistant', content='今天天气不错。'), mock_model)
    )

    query = Mock()
    query.pipeline_config = {'output': {'misc': {'remove-think': False}}}

    result = await runner._polish_local_faq_answer(
        query=query,
        user_message_text='哪个职业好玩',
        matched_question='哪个职业好玩？',
        standard_answer='鬼王前期开荒更快，焚天更适合中后期团战。',
    )

    assert result == '鬼王前期开荒更快，焚天更适合中后期团战。'


@pytest.mark.asyncio
async def test_polish_local_faq_answer_falls_back_when_model_raises():
    from langbot.pkg.provider.runners.localagent import LocalAgentRunner

    mock_app = Mock()
    mock_app.logger = Mock()
    runner = LocalAgentRunner(mock_app, pipeline_config={})

    runner._get_model_candidates = AsyncMock(return_value=[Mock()])
    runner._invoke_with_fallback = AsyncMock(side_effect=RuntimeError('model failed'))

    query = Mock()
    query.pipeline_config = {'output': {'misc': {'remove-think': False}}}

    result = await runner._polish_local_faq_answer(
        query=query,
        user_message_text='哪个职业好玩',
        matched_question='哪个职业好玩？',
        standard_answer='鬼王前期开荒更快，焚天更适合中后期团战。',
    )

    assert result == '鬼王前期开荒更快，焚天更适合中后期团战。'


@pytest.mark.asyncio
async def test_run_prefers_bound_knowledge_base_over_local_faq():
    import langbot_plugin.api.entities.builtin.provider.message as provider_message

    from langbot.pkg.provider.runners.localagent import LocalAgentRunner

    mock_app = Mock()
    mock_app.logger = Mock()
    mock_app.rag_mgr = Mock()

    runtime_kb = Mock()
    runtime_kb.retrieve = AsyncMock(
        return_value=[
            SimpleNamespace(
                metadata={
                    'local_faq_answer': '知识库里的直播间答复',
                    'matched_question': '有直播间吗',
                },
                content=[],
            )
        ]
    )
    mock_app.rag_mgr.get_knowledge_base_by_uuid = AsyncMock(return_value=runtime_kb)

    runner = LocalAgentRunner(mock_app, pipeline_config={})
    runner._match_local_faq_answer = Mock(return_value='代码 JSON 里的答复')

    async def _return_standard_answer(**kwargs):
        return kwargs['standard_answer']

    runner._polish_local_faq_answer = AsyncMock(side_effect=_return_standard_answer)

    query = Mock()
    query.variables = {'_knowledge_base_uuids': ['kb-live-room']}
    query.user_message = provider_message.Message(role='user', content='有直播间吗')
    query.adapter = Mock()
    query.adapter.is_stream_output_supported = AsyncMock(return_value=False)
    query.pipeline_config = {
        'ai': {
            'local-agent': {
                'local-faq-enabled': True,
                'local-faq-path': 'res/local_faq/wecom_agentic_faq.json',
            }
        },
        'output': {'misc': {'remove-think': False}},
    }
    query.prompt = SimpleNamespace(messages=[])
    query.messages = []
    query.bot_uuid = 'bot-1'
    query.sender_id = 'user-1'
    query.session = SimpleNamespace(
        launcher_type=SimpleNamespace(value='person'),
        launcher_id='user-1',
    )

    result = [message async for message in runner.run(query)]

    assert len(result) == 1
    assert result[0].content == '知识库里的直播间答复'
    runner._match_local_faq_answer.assert_not_called()
