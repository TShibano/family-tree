from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Sex(Enum):
    M = "M"
    F = "F"


@dataclass
class Person:
    """個人情報を表すデータクラス。

    必須フィールドに加え、未知のカラムは metadata 辞書に保持する。
    """

    id: int
    name: str
    birth_date: date
    sex: Sex
    parent_ids: list[int] = field(default_factory=list)
    spouse_id: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class Family:
    """家族全体を管理するデータクラス。"""

    persons: dict[int, Person] = field(default_factory=dict)

    def add_person(self, person: Person) -> None:
        self.persons[person.id] = person

    def get_person(self, person_id: int) -> Person | None:
        return self.persons.get(person_id)

    def get_children(self, person_id: int) -> list[Person]:
        """指定された人物の子供を返す。"""
        return [
            p
            for p in self.persons.values()
            if person_id in p.parent_ids
        ]

    def get_parents(self, person_id: int) -> list[Person]:
        """指定された人物の親を返す。"""
        person = self.persons.get(person_id)
        if person is None:
            return []
        return [
            self.persons[pid]
            for pid in person.parent_ids
            if pid in self.persons
        ]

    def get_spouse(self, person_id: int) -> Person | None:
        """指定された人物の配偶者を返す。"""
        person = self.persons.get(person_id)
        if person is None or person.spouse_id is None:
            return None
        return self.persons.get(person.spouse_id)
