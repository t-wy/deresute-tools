from enum import Enum

import customlogger as logger
from db import db


class Difficulty(Enum):
    DEBUT = 1
    REGULAR = 2
    PRO = 3
    MASTER = 4
    MPLUS = 5
    WITCH = 6
    LEGACY = 101
    LIGHT = 11
    TRICK = 12
    PIANO = 21
    FORTE = 22


FLICK_DRAIN = {
    Difficulty.LIGHT: 0,
    Difficulty.TRICK: 8,
    Difficulty.DEBUT: 0,
    Difficulty.REGULAR: 0,
    Difficulty.PRO: 8,
    Difficulty.MASTER: 10,
    Difficulty.MPLUS: 10,
    Difficulty.WITCH: 10,
    Difficulty.LEGACY: 10,
    Difficulty.PIANO: 10,
    Difficulty.FORTE: 10,
}

NONFLICK_DRAIN = {
    Difficulty.LIGHT: 10,
    Difficulty.TRICK: 15,
    Difficulty.DEBUT: 10,
    Difficulty.REGULAR: 12,
    Difficulty.PRO: 15,
    Difficulty.MASTER: 20,
    Difficulty.MPLUS: 20,
    Difficulty.WITCH: 20,
    Difficulty.LEGACY: 20,
    Difficulty.PIANO: 10,
    Difficulty.FORTE: 10,
}

FLICK_BAD_DRAIN = {
    Difficulty.LIGHT: 0,
    Difficulty.TRICK: 5,
    Difficulty.DEBUT: 0,
    Difficulty.REGULAR: 0,
    Difficulty.PRO: 5,
    Difficulty.MASTER: 6,
    Difficulty.MPLUS: 6,
    Difficulty.WITCH: 6,
    Difficulty.LEGACY: 6,
    Difficulty.PIANO: 6,
    Difficulty.FORTE: 6,
}

NONFLICK_BAD_DRAIN = {
    Difficulty.LIGHT: 6,
    Difficulty.TRICK: 9,
    Difficulty.DEBUT: 6,
    Difficulty.REGULAR: 7,
    Difficulty.PRO: 9,
    Difficulty.MASTER: 12,
    Difficulty.MPLUS: 12,
    Difficulty.WITCH: 12,
    Difficulty.LEGACY: 12,
    Difficulty.PIANO: 6,
    Difficulty.FORTE: 6,
}

BAD_TAP_RANGE = {
    Difficulty.LIGHT: 180000,
    Difficulty.TRICK: 140000,
    Difficulty.DEBUT: 180000,
    Difficulty.REGULAR: 180000,
    Difficulty.PRO: 140000,
    Difficulty.MASTER: 130000,
    Difficulty.MPLUS: 130000,
    Difficulty.WITCH: 130000,
    Difficulty.LEGACY: 130000,
    Difficulty.PIANO: 130000,
    Difficulty.FORTE: 130000,
}

NICE_TAP_RANGE = {
    Difficulty.LIGHT: 150000,
    Difficulty.TRICK: 110000,
    Difficulty.DEBUT: 150000,
    Difficulty.REGULAR: 150000,
    Difficulty.PRO: 110000,
    Difficulty.MASTER: 100000,
    Difficulty.MPLUS: 100000,
    Difficulty.WITCH: 100000,
    Difficulty.LEGACY: 100000,
    Difficulty.PIANO: 100000,
    Difficulty.FORTE: 100000,
}

GREAT_TAP_RANGE = {
    Difficulty.LIGHT: 120000,
    Difficulty.TRICK: 90000,
    Difficulty.DEBUT: 120000,
    Difficulty.REGULAR: 120000,
    Difficulty.PRO: 90000,
    Difficulty.MASTER: 80000,
    Difficulty.MPLUS: 80000,
    Difficulty.WITCH: 80000,
    Difficulty.LEGACY: 80000,
    Difficulty.PIANO: 80000,
    Difficulty.FORTE: 80000,
}

PERFECT_TAP_RANGE = {
    Difficulty.LIGHT: 80000,
    Difficulty.TRICK: 70000,
    Difficulty.DEBUT: 80000,
    Difficulty.REGULAR: 80000,
    Difficulty.PRO: 70000,
    Difficulty.MASTER: 60000,
    Difficulty.MPLUS: 60000,
    Difficulty.WITCH: 60000,
    Difficulty.LEGACY: 60000,
    Difficulty.PIANO: 60000,
    Difficulty.FORTE: 60000,
}

logger.debug("Creating chihiro.difficulty_text...")

db.cachedb.execute(""" DROP TABLE IF EXISTS difficulty_text """)
db.cachedb.execute("""
    CREATE TABLE IF NOT EXISTS difficulty_text (
        "id" INTEGER UNIQUE PRIMARY KEY,
        "text" TEXT UNIQUE
    )
""")
for diff in Difficulty:
    db.cachedb.execute("""
        INSERT OR IGNORE INTO difficulty_text ("id", "text")
        VALUES (?,?)
    """, [diff.value, diff.name.replace("MPLUS", "Master+").capitalize()])
db.cachedb.commit()

logger.debug("chihiro.difficulty_text created.")
