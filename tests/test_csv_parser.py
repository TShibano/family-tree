from __future__ import annotations

import textwrap
from datetime import date
from pathlib import Path

import pytest

from family_tree.csv_parser import CsvParseError, parse_csv
from family_tree.models import Sex


@pytest.fixture()
def sample_csv(tmp_path: Path) -> Path:
    """最小限のサンプルCSVを作成する。"""
    csv_content = textwrap.dedent("""\
        id,name,birth_date,sex,parent_ids,spouse_id
        1,太郎,1940-03-15,M,,2
        2,花子,1942-07-22,F,,1
        3,一郎,1965-01-10,M,"1,2",4
        4,美咲,1967-05-30,F,,3
    """)
    csv_path = tmp_path / "test.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    return csv_path


class TestParseCSV:
    def test_parse_basic(self, sample_csv: Path) -> None:
        family = parse_csv(sample_csv)
        assert len(family.persons) == 4

    def test_person_fields(self, sample_csv: Path) -> None:
        family = parse_csv(sample_csv)
        taro = family.get_person(1)
        assert taro is not None
        assert taro.name == "太郎"
        assert taro.birth_date == date(1940, 3, 15)
        assert taro.sex == Sex.M
        assert taro.parent_ids == []
        assert taro.spouse_id == 2

    def test_parent_ids_parsed(self, sample_csv: Path) -> None:
        family = parse_csv(sample_csv)
        ichiro = family.get_person(3)
        assert ichiro is not None
        assert ichiro.parent_ids == [1, 2]

    def test_empty_spouse_id(self, sample_csv: Path) -> None:
        """spouse_id が空の場合は None になる。"""
        csv_content = textwrap.dedent("""\
            id,name,birth_date,sex,parent_ids,spouse_id
            1,太郎,1940-03-15,M,,
        """)
        csv_path = sample_csv.parent / "no_spouse.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        family = parse_csv(csv_path)
        assert family.get_person(1) is not None
        assert family.get_person(1).spouse_id is None  # type: ignore[union-attr]

    def test_family_get_children(self, sample_csv: Path) -> None:
        family = parse_csv(sample_csv)
        children = family.get_children(1)
        assert len(children) == 1
        assert children[0].name == "一郎"

    def test_family_get_parents(self, sample_csv: Path) -> None:
        family = parse_csv(sample_csv)
        parents = family.get_parents(3)
        assert len(parents) == 2
        names = {p.name for p in parents}
        assert names == {"太郎", "花子"}

    def test_family_get_spouse(self, sample_csv: Path) -> None:
        family = parse_csv(sample_csv)
        spouse = family.get_spouse(1)
        assert spouse is not None
        assert spouse.name == "花子"


class TestMetadata:
    def test_extra_columns_stored_as_metadata(self, tmp_path: Path) -> None:
        """未知のカラムはメタデータとして保持される。"""
        csv_content = textwrap.dedent("""\
            id,name,birth_date,sex,parent_ids,spouse_id,occupation,notes
            1,太郎,1940-03-15,M,,,エンジニア,備考テスト
        """)
        csv_path = tmp_path / "meta.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        family = parse_csv(csv_path)
        taro = family.get_person(1)
        assert taro is not None
        assert taro.metadata["occupation"] == "エンジニア"
        assert taro.metadata["notes"] == "備考テスト"

    def test_empty_extra_columns_not_stored(self, tmp_path: Path) -> None:
        """空の未知カラムはメタデータに含まれない。"""
        csv_content = textwrap.dedent("""\
            id,name,birth_date,sex,parent_ids,spouse_id,occupation
            1,太郎,1940-03-15,M,,,
        """)
        csv_path = tmp_path / "meta_empty.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        family = parse_csv(csv_path)
        taro = family.get_person(1)
        assert taro is not None
        assert "occupation" not in taro.metadata


class TestValidation:
    def test_missing_required_column(self, tmp_path: Path) -> None:
        csv_content = textwrap.dedent("""\
            id,name,birth_date,sex,parent_ids
            1,太郎,1940-03-15,M,
        """)
        csv_path = tmp_path / "missing_col.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        with pytest.raises(CsvParseError, match="必須カラムが不足"):
            parse_csv(csv_path)

    def test_duplicate_id(self, tmp_path: Path) -> None:
        csv_content = textwrap.dedent("""\
            id,name,birth_date,sex,parent_ids,spouse_id
            1,太郎,1940-03-15,M,,
            1,花子,1942-07-22,F,,
        """)
        csv_path = tmp_path / "dup_id.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        with pytest.raises(CsvParseError, match="IDが重複"):
            parse_csv(csv_path)

    def test_invalid_parent_reference(self, tmp_path: Path) -> None:
        csv_content = textwrap.dedent("""\
            id,name,birth_date,sex,parent_ids,spouse_id
            1,太郎,1940-03-15,M,,
            2,一郎,1965-01-10,M,"1,99",
        """)
        csv_path = tmp_path / "bad_parent.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        with pytest.raises(CsvParseError, match="参照整合性エラー"):
            parse_csv(csv_path)

    def test_invalid_spouse_reference(self, tmp_path: Path) -> None:
        csv_content = textwrap.dedent("""\
            id,name,birth_date,sex,parent_ids,spouse_id
            1,太郎,1940-03-15,M,,99
        """)
        csv_path = tmp_path / "bad_spouse.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        with pytest.raises(CsvParseError, match="参照整合性エラー"):
            parse_csv(csv_path)

    def test_invalid_sex_value(self, tmp_path: Path) -> None:
        csv_content = textwrap.dedent("""\
            id,name,birth_date,sex,parent_ids,spouse_id
            1,太郎,1940-03-15,X,,
        """)
        csv_path = tmp_path / "bad_sex.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        with pytest.raises(CsvParseError, match="不正な性別値"):
            parse_csv(csv_path)

    def test_invalid_date(self, tmp_path: Path) -> None:
        csv_content = textwrap.dedent("""\
            id,name,birth_date,sex,parent_ids,spouse_id
            1,太郎,not-a-date,M,,
        """)
        csv_path = tmp_path / "bad_date.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        with pytest.raises(CsvParseError, match="2行目"):
            parse_csv(csv_path)

    def test_empty_name(self, tmp_path: Path) -> None:
        csv_content = textwrap.dedent("""\
            id,name,birth_date,sex,parent_ids,spouse_id
            1,,1940-03-15,M,,
        """)
        csv_path = tmp_path / "empty_name.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        with pytest.raises(CsvParseError, match="名前が空"):
            parse_csv(csv_path)

    def test_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(CsvParseError, match="ファイルが見つかりません"):
            parse_csv(tmp_path / "nonexistent.csv")

    def test_empty_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("", encoding="utf-8")
        with pytest.raises(CsvParseError, match="CSVファイルが空です"):
            parse_csv(csv_path)


class TestSampleCSV:
    def test_parse_sample_csv(self) -> None:
        """examples/sample.csv が正常に読み込めることを確認。"""
        family = parse_csv("examples/sample.csv")
        assert len(family.persons) == 12
