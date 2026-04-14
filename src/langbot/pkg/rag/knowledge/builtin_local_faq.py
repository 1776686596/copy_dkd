from __future__ import annotations

import csv
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


_XLSX_NS = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
_QUESTION_KEYS = ('问题', 'questions', 'question', '提问')
_ANSWER_KEYS = ('回答', 'answer', '答案')


def parse_local_faq_file(file_path: Path, extension: str) -> list[dict]:
    normalized_extension = extension.lower().lstrip('.')

    if normalized_extension == 'json':
        payload = json.loads(file_path.read_text(encoding='utf-8'))
        if not isinstance(payload, list):
            raise ValueError('Local FAQ JSON file must be a list')

        return [entry for item in payload if (entry := _normalize_entry(item)) is not None]

    if normalized_extension == 'csv':
        with file_path.open('r', encoding='utf-8-sig', newline='') as file:
            reader = csv.DictReader(file)
            return [entry for row in reader if (entry := _normalize_tabular_row(row)) is not None]

    if normalized_extension == 'xlsx':
        return _parse_xlsx_rows(file_path)

    raise ValueError(f'Unsupported local FAQ extension: {extension}')


def build_retrieve_result(
    *,
    entry_id: str,
    question: str,
    answer: str,
    distance: float,
    source_file_id: str | None,
) -> dict:
    return {
        'id': entry_id,
        'distance': distance,
        'metadata': {
            'matched_question': question,
            'source_file_id': source_file_id,
            'local_faq_answer': answer,
        },
        'content': [{'type': 'text', 'text': answer}],
    }


def _normalize_entry(item: object) -> dict | None:
    if not isinstance(item, dict):
        return None

    answer = str(item.get('answer', '')).strip()
    questions = _split_questions(item.get('questions') or item.get('question'))

    if not questions or not answer:
        return None

    return {'questions': questions, 'answer': answer}


def _normalize_tabular_row(row: dict[str, object]) -> dict | None:
    question_value = _first_non_empty_value(row, _QUESTION_KEYS)
    answer_value = _first_non_empty_value(row, _ANSWER_KEYS)

    questions = _split_questions(question_value)
    answer = str(answer_value or '').strip()

    if not questions or not answer:
        return None

    return {'questions': questions, 'answer': answer}


def _first_non_empty_value(row: dict[str, object], keys: tuple[str, ...]) -> object | None:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _split_questions(raw_questions: object) -> list[str]:
    if raw_questions is None:
        return []

    if isinstance(raw_questions, list):
        parts = raw_questions
    else:
        parts = [raw_questions]

    questions: list[str] = []
    for part in parts:
        text = str(part).strip()
        if not text:
            continue
        for segment in re.split(r'[\n\r;；]+', text):
            normalized = segment.strip()
            if normalized:
                questions.append(normalized)

    return questions


def _parse_xlsx_rows(file_path: Path) -> list[dict]:
    with ZipFile(file_path) as archive:
        shared_strings = _read_shared_strings(archive)
        worksheet_path = _resolve_first_worksheet_path(archive)
        rows = _read_sheet_rows(archive, worksheet_path, shared_strings)

    if not rows:
        return []

    headers = [str(value).strip() for value in rows[0]]
    entries: list[dict] = []
    for values in rows[1:]:
        row = {
            headers[index]: values[index] if index < len(values) else ''
            for index in range(len(headers))
            if headers[index]
        }
        entry = _normalize_tabular_row(row)
        if entry is not None:
            entries.append(entry)

    return entries


def _resolve_first_worksheet_path(archive: ZipFile) -> str:
    worksheet_paths = sorted(
        name
        for name in archive.namelist()
        if name.startswith('xl/worksheets/') and name.endswith('.xml')
    )
    if not worksheet_paths:
        raise ValueError('Local FAQ xlsx file does not contain any worksheet')
    return worksheet_paths[0]


def _read_shared_strings(archive: ZipFile) -> list[str]:
    if 'xl/sharedStrings.xml' not in archive.namelist():
        return []

    root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
    values: list[str] = []
    for item in root.findall('main:si', _XLSX_NS):
        text = ''.join(node.text or '' for node in item.findall('.//main:t', _XLSX_NS))
        values.append(text)
    return values


def _read_sheet_rows(archive: ZipFile, worksheet_path: str, shared_strings: list[str]) -> list[list[str]]:
    root = ET.fromstring(archive.read(worksheet_path))
    rows: list[list[str]] = []

    for row_node in root.findall('main:sheetData/main:row', _XLSX_NS):
        values_by_index: dict[int, str] = {}
        for cell in row_node.findall('main:c', _XLSX_NS):
            cell_ref = cell.attrib.get('r', '')
            cell_index = _column_index(cell_ref)
            values_by_index[cell_index] = _read_cell_value(cell, shared_strings)

        if not values_by_index:
            continue

        max_index = max(values_by_index)
        rows.append([values_by_index.get(index, '') for index in range(max_index + 1)])

    return rows


def _column_index(cell_ref: str) -> int:
    column_name = ''.join(char for char in cell_ref if char.isalpha()).upper()
    index = 0
    for char in column_name:
        index = index * 26 + (ord(char) - ord('A') + 1)
    return max(index - 1, 0)


def _read_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get('t')
    value_node = cell.find('main:v', _XLSX_NS)

    if cell_type == 'inlineStr':
        return ''.join(node.text or '' for node in cell.findall('.//main:t', _XLSX_NS))

    if value_node is None or value_node.text is None:
        return ''

    if cell_type == 's':
        shared_index = int(value_node.text)
        if 0 <= shared_index < len(shared_strings):
            return shared_strings[shared_index]
        return ''

    return value_node.text
