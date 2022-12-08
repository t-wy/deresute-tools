from db import db


def initialize_personal_units():
    db.cachedb.execute("DROP TABLE IF EXISTS personal_units")
    db.cachedb.execute("""
        CREATE TABLE personal_units (
            unit_id INTEGER PRIMARY KEY,
            unit_name TEXT,
            grand INTEGER,
            cards BLOB
        )""")
    db.cachedb.commit()


def add_empty_unit() -> int:
    db.cachedb.execute("INSERT INTO personal_units (unit_name, grand, cards) VALUES (?,?,?)",
                       ["", 0, ",,,,"])
    db.cachedb.commit()
    return db.cachedb.execute_and_fetchone("SELECT last_insert_rowid()")[0]


def update_unit(unit_id: int, unit_name: str, cards: list[int], grand: bool = False):
    if isinstance(cards, list):
        cards = ["" if _ is None else str(_) for _ in cards]
        cards = ",".join(cards)
    db.cachedb.execute("UPDATE personal_units SET unit_name = ?, grand = ?, cards = ? WHERE unit_id = ?",
                       [unit_name, grand, cards, unit_id])
    db.cachedb.commit()


def delete_unit(unit_id: int):
    db.cachedb.execute("DELETE FROM personal_units WHERE unit_id = ? ", [unit_id])
    db.cachedb.commit()


def clean_all_units(grand: bool = False):
    grand = 1 if grand else 0
    db.cachedb.execute("DELETE FROM personal_units WHERE grand = ? ", [grand])
    db.cachedb.commit()
