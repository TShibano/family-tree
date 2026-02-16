from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from family_tree.models import Family, Person, Sex

REQUIRED_COLUMNS = {"id", "name", "birth_date", "sex", "parent_ids", "spouse_id"}


class CsvParseError(Exception):
    """CSV読み込み時のエラー。"""


def parse_csv(path: str | Path) -> Family:
    """CSVファイルを読み込み、Family オブジェクトを返す。

    Args:
        path: CSVファイルのパス

    Returns:
        Family オブジェクト

    Raises:
        CsvParseError: CSV読み込み・バリデーションエラー
    """
    path = Path(path)
    if not path.exists():
        raise CsvParseError(f"ファイルが見つかりません: {path}")

    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise CsvParseError("CSVファイルが空です")

        headers = set(reader.fieldnames)
        _validate_columns(headers)

        extra_columns = headers - REQUIRED_COLUMNS
        rows = list(reader)

    persons = _parse_rows(rows, extra_columns)
    family = Family()
    for person in persons:
        family.add_person(person)

    _validate_references(family)
    return family


def _validate_columns(headers: set[str]) -> None:
    """必須カラムの存在を確認する。"""
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise CsvParseError(f"必須カラムが不足しています: {', '.join(sorted(missing))}")


def _parse_rows(
    rows: list[dict[str, str]], extra_columns: set[str]
) -> list[Person]:
    """CSV行をPersonオブジェクトのリストに変換する。"""
    persons: list[Person] = []
    seen_ids: set[int] = set()

    for i, row in enumerate(rows, start=2):  # ヘッダー行が1行目
        try:
            person = _parse_row(row, extra_columns)
        except (ValueError, KeyError) as e:
            raise CsvParseError(f"{i}行目: {e}") from e

        if person.id in seen_ids:
            raise CsvParseError(f"{i}行目: IDが重複しています: {person.id}")
        seen_ids.add(person.id)
        persons.append(person)

    return persons


def _parse_row(row: dict[str, str], extra_columns: set[str]) -> Person:
    """1行のCSVデータをPersonオブジェクトに変換する。"""
    person_id = int(row["id"])
    name = row["name"].strip()
    if not name:
        raise ValueError("名前が空です")

    birth_date = date.fromisoformat(row["birth_date"])

    sex_str = row["sex"].strip().upper()
    try:
        sex = Sex(sex_str)
    except ValueError:
        raise ValueError(f"不正な性別値です: {row['sex']}")

    parent_ids_str = row["parent_ids"].strip()
    parent_ids: list[int] = []
    if parent_ids_str:
        parent_ids = [int(pid.strip()) for pid in parent_ids_str.split(",")]

    spouse_id_str = row["spouse_id"].strip()
    spouse_id: int | None = int(spouse_id_str) if spouse_id_str else None

    metadata: dict[str, str] = {}
    for col in extra_columns:
        value = row.get(col, "")
        if value:
            metadata[col] = value

    return Person(
        id=person_id,
        name=name,
        birth_date=birth_date,
        sex=sex,
        parent_ids=parent_ids,
        spouse_id=spouse_id,
        metadata=metadata,
    )


def _validate_references(family: Family) -> None:
    """参照整合性を検証する。"""
    all_ids = set(family.persons.keys())
    errors: list[str] = []

    for person in family.persons.values():
        for pid in person.parent_ids:
            if pid not in all_ids:
                errors.append(
                    f"ID {person.id} ({person.name}): "
                    f"親ID {pid} が存在しません"
                )

        if person.spouse_id is not None and person.spouse_id not in all_ids:
            errors.append(
                f"ID {person.id} ({person.name}): "
                f"配偶者ID {person.spouse_id} が存在しません"
            )

    if errors:
        raise CsvParseError(
            "参照整合性エラー:\n" + "\n".join(f"  - {e}" for e in errors)
        )
