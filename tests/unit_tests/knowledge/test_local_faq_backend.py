from __future__ import annotations

import csv
import json
from pathlib import Path
from zipfile import ZipFile


def _write_csv_faq(path: Path) -> None:
    with path.open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['问题', '回答'])
        writer.writeheader()
        writer.writerow(
            {
                '问题': '哪个职业好玩？\n职业推荐',
                '回答': '鬼王前期开荒更快，焚天更适合中后期团战。',
            }
        )


def _write_xlsx_faq(path: Path) -> None:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""
    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>
"""
    shared_strings = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="4" uniqueCount="4">
  <si><t>问题</t></si>
  <si><t>回答</t></si>
  <si><t>礼包码；福利</t></si>
  <si><t>下载注册后把区服和角色名给我，我给你安排礼包和 CDK。</t></si>
</sst>
"""
    sheet = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="s"><v>0</v></c>
      <c r="B1" t="s"><v>1</v></c>
    </row>
    <row r="2">
      <c r="A2" t="s"><v>2</v></c>
      <c r="B2" t="s"><v>3</v></c>
    </row>
  </sheetData>
</worksheet>
"""
    with ZipFile(path, 'w') as archive:
        archive.writestr('[Content_Types].xml', content_types)
        archive.writestr('_rels/.rels', rels)
        archive.writestr('xl/workbook.xml', workbook)
        archive.writestr('xl/_rels/workbook.xml.rels', workbook_rels)
        archive.writestr('xl/sharedStrings.xml', shared_strings)
        archive.writestr('xl/worksheets/sheet1.xml', sheet)


def test_parse_json_faq_file_reads_questions_and_answer(tmp_path: Path):
    from langbot.pkg.rag.knowledge.builtin_local_faq import parse_local_faq_file

    file_path = tmp_path / 'faq.json'
    file_path.write_text(
        json.dumps(
            [
                {
                    'questions': ['哪个职业好玩？', '职业推荐'],
                    'answer': '鬼王前期开荒更快，焚天更适合中后期团战。',
                }
            ],
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    entries = parse_local_faq_file(file_path, extension='json')

    assert len(entries) == 1
    assert entries[0]['questions'] == ['哪个职业好玩？', '职业推荐']
    assert entries[0]['answer'] == '鬼王前期开荒更快，焚天更适合中后期团战。'


def test_parse_csv_faq_file_splits_multiple_questions(tmp_path: Path):
    from langbot.pkg.rag.knowledge.builtin_local_faq import parse_local_faq_file

    file_path = tmp_path / 'faq.csv'
    _write_csv_faq(file_path)

    entries = parse_local_faq_file(file_path, extension='csv')

    assert len(entries) == 1
    assert entries[0]['questions'] == ['哪个职业好玩？', '职业推荐']
    assert entries[0]['answer'] == '鬼王前期开荒更快，焚天更适合中后期团战。'


def test_parse_xlsx_faq_file_reads_rows(tmp_path: Path):
    from langbot.pkg.rag.knowledge.builtin_local_faq import parse_local_faq_file

    file_path = tmp_path / 'faq.xlsx'
    _write_xlsx_faq(file_path)

    entries = parse_local_faq_file(file_path, extension='xlsx')

    assert len(entries) == 1
    assert entries[0]['questions'] == ['礼包码', '福利']
    assert entries[0]['answer'] == '下载注册后把区服和角色名给我，我给你安排礼包和 CDK。'


def test_build_retrieve_result_returns_expected_fields():
    from langbot.pkg.rag.knowledge.builtin_local_faq import build_retrieve_result

    result = build_retrieve_result(
        entry_id='entry-1',
        question='哪个职业好玩？',
        answer='鬼王前期开荒更快，焚天更适合中后期团战。',
        distance=0.01,
        source_file_id='file-1',
    )

    assert result['id'] == 'entry-1'
    assert result['metadata']['matched_question'] == '哪个职业好玩？'
    assert result['metadata']['source_file_id'] == 'file-1'
    assert result['metadata']['local_faq_answer'] == '鬼王前期开荒更快，焚天更适合中后期团战。'
    assert result['content'][0]['text'] == '鬼王前期开荒更快，焚天更适合中后期团战。'
