from __future__ import annotations


_TRANSFER_REPLY = '我帮您转接人工客服继续处理'


def _sanitize_customer_service_copy(value: str) -> str:
    sanitized = value

    for waiting_phrase in ('稍等下哈', '稍等一下', '稍等一下哈'):
        sanitized = sanitized.replace(waiting_phrase, _TRANSFER_REPLY)

    return sanitized


def _normalize_prompt_entries(prompt: object) -> list[dict]:
    if isinstance(prompt, str):
        content = _sanitize_customer_service_copy(prompt.strip())
        if not content:
            return []
        return [{'role': 'system', 'content': content}]

    if not isinstance(prompt, list):
        return []

    normalized_prompt: list[dict] = []
    for entry in prompt:
        if not isinstance(entry, dict):
            continue

        role = entry.get('role')
        content = entry.get('content')

        if not isinstance(content, str):
            continue

        cleaned_content = _sanitize_customer_service_copy(content.strip())
        if not cleaned_content:
            continue

        normalized_prompt.append(
            {
                'role': role if isinstance(role, str) and role.strip() else 'system',
                'content': cleaned_content,
            }
        )

    return normalized_prompt


def _normalize_text(value: object) -> str:
    if not isinstance(value, str):
        return ''
    return _sanitize_customer_service_copy(value.strip())


def compose_game_customer_service_prompt(local_agent_config: dict) -> str:
    application_description = _normalize_text(local_agent_config.get('application-description'))
    application_settings = _normalize_text(local_agent_config.get('application-settings'))
    opening_intro = _normalize_text(local_agent_config.get('opening-intro'))

    content_parts = ['你是【传奇手游】企微专属智能客服。']

    if application_description:
        content_parts.append(f'应用描述：{application_description}')
    if application_settings:
        content_parts.append(f'应用设定：{application_settings}')
    if opening_intro:
        content_parts.append(f'开场介绍参考：{opening_intro}')

    content_parts.extend(
        [
            '执行要求：',
            '1. 严格优先依据知识库回复，知识库命中时不要脱离知识库自由发挥；同一问题若有多个候选答案，任选 1 个输出，并尽量避免同会话重复。',
            '2. 回复简洁自然，贴合老玩家语气，不要太长，不要生硬营销；暂时不要主动推送复古版本内容。',
            '3. 若需要推荐下载：单职业无限刀版本推荐御龙无双 https://g.guayou.com/?ct=shouyou&ac=h5&gid=63&member=639；超变版本推荐战谷 https://g.guayou.com/?ct=shouyou&ac=h5&gid=68&member=217；发送下载链接后追加“麻烦老板按区服：XX区 角色名：XXX的格式发送给我”。',
            '4. 始终执行敏感词过滤，并将“福利”统一替换为“福～利”。',
            '5. 若触发人工介入、高意向深度咨询、下载注册障碍、负面质疑、要求人工、提交区服角色名或旧账号复杂问题，直接说明：我帮您转接人工客服继续处理。不要追加营销内容。',
            '6. 若知识库暂未覆盖，不要编造答案；优先基于已知信息给出最接近的有效答复，必要时只追问一个关键问题。',
        ]
    )

    return '\n'.join(content_parts)


def build_local_agent_prompt_config(local_agent_config: dict | None) -> list[dict]:
    local_agent_config = local_agent_config or {}

    normalized_prompt = _normalize_prompt_entries(local_agent_config.get('prompt'))
    if local_agent_config.get('show-advanced-prompt') and normalized_prompt:
        return normalized_prompt

    has_business_fields = any(
        _normalize_text(local_agent_config.get(field))
        for field in ('application-settings', 'application-description', 'opening-intro')
    )
    if has_business_fields:
        return [{'role': 'system', 'content': compose_game_customer_service_prompt(local_agent_config)}]

    if normalized_prompt:
        return normalized_prompt

    return [{'role': 'system', 'content': compose_game_customer_service_prompt(local_agent_config)}]
