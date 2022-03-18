import customlogger as logger
from db import db

SKILL_BASE = {0: "",
              1: "Cute Voice",
              2: "Cute Step",
              3: "Cute Makeup",
              4: "Cute Brilliance",
              5: "Cute Energy",
              6: "Cool Voice",
              7: "Cool Step",
              8: "Cool Makeup",
              9: "Cool Brilliance",
              10: "Cool Energy",
              11: "Passion Voice",
              12: "Passion Step",
              13: "Passion Makeup",
              14: "Passion Brilliance",
              15: "Passion Energy",
              16: "Shiny Voice",
              17: "Shiny Step",
              18: "Shiny Makeup",
              19: "Shiny Brilliance",
              20: "Shiny Energy",
              21: "Cute Ability",
              22: "Cool Ability",
              23: "Passion Ability",
              24: "Cute Voice",
              25: "Cute Step",
              26: "Cute Makeup",
              27: "Cute Brilliance",
              28: "Cute Energy",
              29: "Cool Voice",
              30: "Cool Step",
              31: "Cool Makeup",
              32: "Cool Brilliance",
              33: "Cool Energy",
              34: "Passion Voice",
              35: "Passion Step",
              36: "Passion Makeup",
              37: "Passion Brilliance",
              38: "Passion Energy",
              39: "Shiny Voice",
              40: "Shiny Step",
              41: "Shiny Makeup",
              42: "Shiny Brilliance",
              43: "Shiny Energy",
              44: "Cute Ability",
              45: "Cool Ability",
              46: "Passion Ability",
              47: "Cute Voice",
              48: "Cute Step",
              49: "Cute Makeup",
              50: "Cute Brilliance",
              51: "Cute Energy",
              52: "Cool Voice",
              53: "Cool Step",
              54: "Cool Makeup",
              55: "Cool Brilliance",
              56: "Cool Energy",
              57: "Passion Voice",
              58: "Passion Step",
              59: "Passion Makeup",
              60: "Passion Brilliance",
              61: "Passion Energy",
              62: "Shiny Voice",
              63: "Shiny Step",
              64: "Shiny Makeup",
              65: "Shiny Brilliance",
              66: "Shiny Energy",
              67: "Cute Ability",
              68: "Cool Ability",
              69: "Passion Ability",
              70: "Tricolor Voice",
              71: "Tricolor Step",
              72: "Tricolor Makeup",
              73: "Tricolor Ability",
              74: "Cute Princess",
              75: "Cool Princess",
              76: "Passion Princess",
              77: "Cute Cheer",
              78: "Cool Cheer",
              79: "Passion Cheer",
              80: "Fortune Present",
              81: "Cinderella Charm",
              82: "Tricolor Voice",
              83: "Tricolor Step",
              84: "Tricolor Makeup",
              85: "Christmas Present",
              86: "Cute Princess",
              87: "Cool Princess",
              88: "Passion Princess",
              89: "CutexCool",
              90: "CutexPassion",
              91: "CoolxCute",
              92: "CoolxPassion",
              93: "PassionxCute",
              94: "PassionxCool",
              101: "Cute Unison",
              102: "Cool Unison",
              103: "Passion Unison",
              104: "Resonance Voice",
              105: "Resonance Step",
              106: "Resonance Makeup",
              107: "CutexCool",
              108: "CutexPassion",
              109: "CoolxCute",
              110: "CoolxPassion",
              111: "PassionxCute",
              112: "PassionxCool",
              113: "Cinderella Yell",
              114: "Tricolor Ability",
              115: "Cinderella Charm",
              116: "World Level",
              117: "Cinderella Wish",
              118: "Cinderella Bless",
              119: "Cute Duet Voice&Step",
              120: "Cute Duet Step&Make",
              121: "Cute Duet Make&Voice",
              122: "Cool Duet Voice&Step",
              123: "Cool Duet Step&Make",
              124: "Cool Duet Make&Voice",
              125: "Passion Duet Voice&Step",
              126: "Passion Duet Step&Make",
              127: "Passion Duet Make&Voice",
              }

logger.debug("Creating chihiro.leader_keywords...")

db.cachedb.execute(""" DROP TABLE IF EXISTS leader_keywords """)
db.cachedb.execute("""
    CREATE TABLE IF NOT EXISTS leader_keywords (
        "id" INTEGER UNIQUE PRIMARY KEY,
        "keywords" TEXT
    )
""")
for skill_id, skill_data in SKILL_BASE.items():
    db.cachedb.execute("""
        INSERT OR IGNORE INTO leader_keywords ("id", "keywords")
        VALUES (?,?)
    """, [skill_id, skill_data])
db.cachedb.commit()

logger.debug("chihiro.leader_keywords created.")
