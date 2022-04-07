from collections import OrderedDict

import customlogger as logger
from db import db

SKILL_BASE = {
    0: {"id": 0, "name": "", "keywords": [], "color": (255, 255, 255)},
    1: {"id": 1, "name": "SCORE Bonus", "keywords": ["su"], "color": (255, 101, 60)},
    2: {"id": 2, "name": "SCORE Bonus", "keywords": ["su"], "color": (255, 101, 60)},
    4: {"id": 4, "name": "COMBO Bonus", "keywords": ["cu"], "color": (248, 187, 0)},
    5: {"id": 5, "name": "PERFECT Support", "color": (33, 215, 174)},
    6: {"id": 6, "name": "PERFECT Support", "color": (33, 215, 174)},
    7: {"id": 7, "name": "PERFECT Support", "color": (33, 215, 174)},
    9: {"id": 9, "name": "COMBO Support", "color": (194, 194, 43)},
    12: {"id": 12, "name": "Damage Guard", "keywords": ["dg"], "color": (38, 201, 255)},
    14: {"id": 14, "name": "Overload", "keywords": ["ol"], "color": (200, 58, 140)},
    15: {"id": 15, "name": "Concentration", "keywords": ["cc"], "color": (148, 77, 255)},
    16: {"id": 16, "name": "Encore", "color": (255, 225, 255)},
    17: {"id": 17, "name": "Life Recovery", "keywords": ["healer"], "color": (78, 206, 49)},
    20: {"id": 20, "name": "Skill Boost", "keywords": ["sb"], "color": (253, 58, 54)},
    21: {"id": 21, "name": "Cute Focus", "keywords": ["focus"], "color": (242, 7, 99)},
    22: {"id": 22, "name": "Cool Focus", "keywords": ["focus"], "color": (15, 99, 255)},
    23: {"id": 23, "name": "Passion Focus", "keywords": ["focus"], "color": (248, 171, 7)},
    24: {"id": 24, "name": "All-round", "keywords": ["ar"], "color": (163, 197, 25)},
    25: {"id": 25, "name": "Life Sparkle", "keywords": ["ls"], "color": (255, 187, 96)},
    26: {"id": 26, "name": "Tricolor Synergy", "keywords": ["syn"], "color": (168, 92, 120)},
    27: {"id": 27, "name": "Coordinate", "color": (251, 153, 24)},
    28: {"id": 28, "name": "Long Act", "color": (255, 211, 119)},
    29: {"id": 29, "name": "Flick Act", "color": (119, 206, 222)},
    30: {"id": 30, "name": "Slide Act", "color": (234, 152, 255)},
    31: {"id": 31, "name": "Tuning", "color": (141, 201, 87)},
    32: {"id": 32, "name": "Cute Ensemble", "keywords": ["ens"], "color": (252, 104, 163)},
    33: {"id": 33, "name": "Cool Ensemble", "keywords": ["ens"], "color": (121, 168, 255)},
    34: {"id": 34, "name": "Passion Ensemble", "keywords": ["ens"], "color": (251, 201, 111)},
    35: {"id": 35, "name": "Vocal Motif", "color": (250, 80, 106)},
    36: {"id": 36, "name": "Dance Motif", "color": (77, 198, 217)},
    37: {"id": 37, "name": "Visual Motif", "color": (244, 162, 52)},
    38: {"id": 38, "name": "Tricolor Symphony", "keywords": ["sym"], "color": (205, 160, 177)},
    39: {"id": 39, "name": "Alternate", "keywords": ["alt"], "color": (127, 127, 127)},
    40: {"id": 40, "name": "Refrain", "keywords": ["ref"], "color": (218, 126, 3)},
    41: {"id": 41, "name": "Magic", "keywords": ["mag"], "color": (255, 200, 255)},
    42: {"id": 42, "name": "Mutual", "color": (191, 191, 191)},
}

SKILL_SAMPLE = {
    1: 100001,
    2: 100077,
    4: 100023,
    5: 100027,
    6: 100161,
    7: 100075,
    9: 100055,
    12: 100085,
    14: 100223,
    15: 100361,
    16: 100853,
    17: 100017,
    20: 100395,
    21: 100371,
    22: 200399,
    23: 300377,
    24: 100383,
    25: 100481,
    26: 100499,
    27: 100577,
    28: 100661,
    29: 100663,
    30: 100701,
    31: 100683,
    32: 100707,
    33: 200697,
    34: 300715,
    35: 100963,
    36: 100849,
    37: 100745,
    38: 100797,
    39: 100809,
    40: 100913,
    41: 200945,
    42: 101015
}

SKILL_COLOR_BY_NAME = {
    v['name']: v['color'] for v in SKILL_BASE.values()
}

logger.debug("Creating chihiro.skill_keywords...")

db.cachedb.execute(""" DROP TABLE IF EXISTS skill_keywords """)
db.cachedb.execute("""
    CREATE TABLE IF NOT EXISTS skill_keywords (
        "id" INTEGER UNIQUE PRIMARY KEY,
        "skill_name" TEXT,
        "keywords" TEXT
    )
""")
for skill_id, skill_data in SKILL_BASE.items():
    db.cachedb.execute("""
        INSERT OR IGNORE INTO skill_keywords ("id", "skill_name", "keywords")
        VALUES (?,?,?)
    """, [skill_id,
          skill_data['name'],
          skill_data['name'] + " " + " ".join(skill_data['keywords'])
                                 if 'keywords' in skill_data
                                 else skill_data['name']])
db.cachedb.commit()

logger.debug("chihiro.skill_keywords created.")

SPARKLE_BONUS_SSR = OrderedDict({_[0]: _[1] for idx, _ in
                     enumerate(db.masterdb.execute_and_fetchall("SELECT life_value / 10, type_01_value FROM skill_life_value ORDER BY life_value"))})
SPARKLE_BONUS_SR = OrderedDict({_[0]: _[1] for idx, _ in
                    enumerate(db.masterdb.execute_and_fetchall("SELECT life_value / 10, type_02_value FROM skill_life_value ORDER BY life_value"))})
SPARKLE_BONUS_SSR_GRAND = OrderedDict({_[0]: _[1] for idx, _ in enumerate(
    db.masterdb.execute_and_fetchall("SELECT life_value / 10, type_01_value FROM skill_life_value_grand ORDER BY life_value"))})
SPARKLE_BONUS_SR_GRAND = OrderedDict({_[0]: _[1] for idx, _ in enumerate(
    db.masterdb.execute_and_fetchall("SELECT life_value / 10, type_02_value FROM skill_life_value_grand ORDER BY life_value"))})

for d in [SPARKLE_BONUS_SSR, SPARKLE_BONUS_SR, SPARKLE_BONUS_SSR_GRAND, SPARKLE_BONUS_SR_GRAND]:
    c_v = 0
    for key, value in d.items():
        if value < c_v:
            d[key] = c_v
        if c_v < value:
            c_v = value

def get_sparkle_bonus(rarity, grand=False):
    if grand:
        if rarity > 6:
            return SPARKLE_BONUS_SSR_GRAND
        if rarity > 4:
            return SPARKLE_BONUS_SR_GRAND
    else:
        if rarity > 6:
            return SPARKLE_BONUS_SSR
        if rarity > 4:
            return SPARKLE_BONUS_SR
