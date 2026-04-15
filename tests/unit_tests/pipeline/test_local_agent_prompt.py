from __future__ import annotations


def test_build_local_agent_prompt_uses_business_fields():
    from langbot.pkg.pipeline.preproc.local_agent_prompt import build_local_agent_prompt_config

    prompt = build_local_agent_prompt_config(
        {
            'application-settings': '适配老玩家的传奇游戏智能客服，优先依据知识库回答。',
            'application-description': '智能客服机器人',
            'opening-intro': '老板你好呀！专属新游福～利来啦🎁',
            'prompt': [{'role': 'system', 'content': 'legacy prompt'}],
        }
    )

    assert len(prompt) == 1
    assert prompt[0]['role'] == 'system'
    assert '应用描述：智能客服机器人' in prompt[0]['content']
    assert '应用设定：适配老玩家的传奇游戏智能客服，优先依据知识库回答。' in prompt[0]['content']
    assert '开场介绍参考：老板你好呀！专属新游福～利来啦🎁' in prompt[0]['content']
    assert '转接人工客服继续处理' not in prompt[0]['content']
    assert '不要直接说转人工' in prompt[0]['content']
    assert '按当前客服人设自然接话' in prompt[0]['content']


def test_build_local_agent_prompt_falls_back_to_legacy_prompt():
    from langbot.pkg.pipeline.preproc.local_agent_prompt import build_local_agent_prompt_config

    prompt = build_local_agent_prompt_config({'prompt': 'legacy prompt'})

    assert prompt == [{'role': 'system', 'content': 'legacy prompt'}]


def test_build_local_agent_prompt_keeps_custom_waiting_phrase():
    from langbot.pkg.pipeline.preproc.local_agent_prompt import build_local_agent_prompt_config

    prompt = build_local_agent_prompt_config(
        {'prompt': '若玩家提交区服角色名，只回复：稍等下哈。'}
    )

    assert prompt == [{'role': 'system', 'content': '若玩家提交区服角色名，只回复：稍等下哈。'}]


def test_build_local_agent_prompt_prefers_advanced_prompt_when_enabled():
    from langbot.pkg.pipeline.preproc.local_agent_prompt import build_local_agent_prompt_config

    prompt = build_local_agent_prompt_config(
        {
            'application-settings': '这是业务配置',
            'show-advanced-prompt': True,
            'prompt': [{'role': 'system', 'content': 'custom advanced prompt'}],
        }
    )

    assert prompt == [{'role': 'system', 'content': 'custom advanced prompt'}]
