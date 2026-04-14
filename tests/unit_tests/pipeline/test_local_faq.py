from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path


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
