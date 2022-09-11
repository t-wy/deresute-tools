import atexit
import csv
import os
import subprocess
import traceback
from collections import defaultdict

import customlogger as logger
from db import db
from gui.viewmodels import custom_card
from logic.profile import card_storage, potential
from logic.profile import unit_storage
from logic.search import card_query
from network.api_client import get_cards
from settings import PROFILE_PATH
from utils import storage

keys = ["chara_id", "vo", "vi", "da", "li", "sk"]
custom_keys = ["id", "rarity", "image_id", "vocal", "dance", "visual", "life",
               "leader_skill_id", "skill_type", "condition", "available_time_type", "probability_type",
               "value", "value_2", "value_3"]

def import_from_gameid(game_id, option):
    try:
        owned_cards = [_[0] for _ in db.cachedb.execute_and_fetchall("SELECT card_id FROM owned_card WHERE number > 0")]
        db.cachedb.execute("UPDATE owned_card SET number=0")
        db.cachedb.commit()
        if option == 6:
            return owned_cards
        assert len(str(game_id)) == 9
        z = int(game_id)
        assert 0 <= z <= 999999999
        logger.info("Trying to import from ID {}, this might take a while".format(game_id))
        cards = list(map(int, get_cards(game_id)))
        for idx, card in enumerate(cards):
            if card % 2 == 1:
                cards[idx] += 1
        card_dict = defaultdict(int)
        for card in cards:
            card_dict[card] += 1
        if option in (1, 3, 5):
            _ = list()
            for card in card_dict:
                if card_dict[card] > 1:
                    card_dict[card] -= 1
                    _.append(card-1)
            for card in _:
                card_dict[card] += 1
        if option in (2, 3, 4, 5):
            cards_sr = [_[0] for _ in db.cachedb.execute_and_fetchall("SELECT id FROM card_data_cache WHERE rarity = 5 OR rarity = 6") if _[0] < 500000]
            for card in cards_sr:
                card_dict[card] += 1
        if option in (4, 5):
            cards_rn = [_[0] for _ in db.cachedb.execute_and_fetchall("SELECT id FROM card_data_cache WHERE rarity < 5") if _[0] < 500000]
            for card in cards_rn:
                card_dict[card] += 1
        for card_id, number in card_dict.items():
            db.cachedb.execute("""
                INSERT OR REPLACE INTO owned_card (card_id, number)
                VALUES (?,?)
            """, [card_id, number])
        db.cachedb.commit()
        logger.info("Imported {} cards successfully".format(len(card_dict)))
        return list(card_dict.keys())
    except:
        logger.debug(traceback.print_exc())
        logger.info("Failed to import cards")


class ProfileManager:
    def __init__(self):
        if not PROFILE_PATH.exists():
            PROFILE_PATH.mkdir()
        db.cachedb.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                "name" TEXT UNIQUE
            )
        """)
        db.cachedb.commit()
        if not self.switch_profile('main'):
            logger.info("No profile found, creating default profile")
            self.add_profile('main')
            self.switch_profile('main')
        self.profile = 'main'

    def switch_profile(self, profile_name=None):
        profile_id = db.cachedb.execute_and_fetchone("SELECT 1 FROM profiles WHERE name = ?", [profile_name])
        if profile_id is None:
            return False
        self.profile = profile_name
        self._load_cards()
        self._load_potentials()
        self._load_units()
        self._load_custom()
        return True

    def add_profile(self, profile_name):
        if db.cachedb.execute_and_fetchone("SELECT 1 FROM profiles WHERE name = ?", [profile_name]):
            raise ValueError("Profile {} already exists".format(profile_name))
        db.cachedb.execute("INSERT INTO profiles (name) VALUES (?)", [profile_name])
        db.cachedb.commit()
        self.switch_profile(profile_name)

    def delete_profile(self, profile_name):
        db.cachedb.execute("DELETE FROM profiles WHERE name = ?", [profile_name])
        db.cachedb.commit()
        if (PROFILE_PATH / "{}.crd".format(profile_name)).exists():
            (PROFILE_PATH / "{}.crd".format(profile_name)).unlink()
        if (PROFILE_PATH / "{}.ptl".format(profile_name)).exists():
            (PROFILE_PATH / "{}.ptl".format(profile_name)).unlink()
        if (PROFILE_PATH / "{}.unt".format(profile_name)).exists():
            (PROFILE_PATH / "{}.unt".format(profile_name)).unlink()
        if (PROFILE_PATH / "{}.cst".format(profile_name)).exists():
            (PROFILE_PATH / "{}.cst".format(profile_name)).unlink()
        self.switch_profile('main')

    def _initialize_owned_cards_csv(self):
        all_cards = [_[0] for _ in db.masterdb.execute_and_fetchall("SELECT id FROM card_data")]
        if not (PROFILE_PATH / "{}.crd".format(self.profile)).exists():
            with storage.get_writer(PROFILE_PATH / "{}.crd".format(self.profile), 'w') as fw:
                fw.write("card_id,number\n")
                for card_id in all_cards:
                    fw.write("{},0\n".format(card_id))
        return all_cards

    def _load_cards(self):
        card_storage.initialize_owned_cards()
        all_card_ids = set(self._initialize_owned_cards_csv())
        with storage.get_reader(PROFILE_PATH / "{}.crd".format(self.profile), 'r') as fr:
            csv_reader = csv.reader(fr)
            next(csv_reader)  # Skip headers
            for row in csv_reader:
                row = list(map(int, row))
                db.cachedb.execute("""
                    INSERT OR REPLACE INTO owned_card (card_id, number)
                    VALUES (?,?)
                """, row)
                all_card_ids.remove(row[0])
            for missing_id in all_card_ids:
                db.cachedb.execute("""
                                    INSERT OR REPLACE INTO owned_card (card_id, number)
                                    VALUES (?,?)
                                """, [missing_id, 0])
            db.cachedb.commit()

    def _write_owned_cards(self):
        owned_cards = db.cachedb.execute_and_fetchall("SELECT * FROM owned_card", out_dict=True)
        with storage.get_writer(PROFILE_PATH / "{}.crd".format(self.profile), 'w') as fw:
            fw.write("card_id,number\n")
            for owned_card in owned_cards:
                fw.write("{},{}\n".format(owned_card['card_id'], owned_card['number']))

    def _initialize_units_csv(self):
        if not (PROFILE_PATH / "{}.unt".format(self.profile)).exists():
            with storage.get_writer(PROFILE_PATH / "{}.unt".format(self.profile), 'w') as fw:
                fw.write("unit_id,grand,cards\n")

    def _load_units(self):
        unit_storage.initialize_personal_units()
        self._initialize_units_csv()
        with storage.get_reader(PROFILE_PATH / "{}.unt".format(self.profile), 'r') as fr:
            csv_reader = csv.reader(fr)
            next(csv_reader)  # Skip headers
            for row in csv_reader:
                db.cachedb.execute("""
                    INSERT OR REPLACE INTO personal_units (unit_name, grand, cards)
                    VALUES (?,?,?)
                """, row)

    def _write_units(self):
        personal_units = db.cachedb.execute_and_fetchall("SELECT * FROM personal_units", out_dict=True)
        with storage.get_writer(PROFILE_PATH / "{}.unt".format(self.profile), 'w', newline='') as fw:
            csv_writer = csv.writer(fw)
            csv_writer.writerow(["unit_id", "grand", "cards"])
            for unit in personal_units:
                csv_writer.writerow([unit['unit_name'], unit['grand'], unit['cards']])

    def _initialize_potentials_csv(self):
        chara_dict = card_query.get_chara_dict()
        if not (PROFILE_PATH / "{}.ptl".format(self.profile)).exists():
            with storage.get_writer(PROFILE_PATH / "{}.ptl".format(self.profile), 'w') as fw:
                fw.write(",".join(keys) + "\n")
                for chara_id, chara_name in chara_dict.items():
                    fw.write(str(chara_id) + "," + ",".join(["0"] * 5) + "\n")
        else:
            with storage.get_reader(PROFILE_PATH / "{}.ptl".format(self.profile), 'r') as fr:
                csv_reader = csv.reader(fr)
                next(csv_reader)
                for row in csv_reader:
                    chara_dict.pop(int(row[0]))
            with storage.get_writer(PROFILE_PATH / "{}.ptl".format(self.profile), 'a') as fa:
                for chara_id, chara_name in chara_dict.items():
                    fa.write(str(chara_id) + "," + ",".join(["0"] * 5) + "\n")


    def _load_potentials(self):
        potential.initialize_potential_db()
        self._initialize_potentials_csv()
        with storage.get_reader(PROFILE_PATH / "{}.ptl".format(self.profile), 'r') as fr:
            csv_reader = csv.reader(fr)
            next(csv_reader)  # Skip headers
            for row in csv_reader:
                db.cachedb.execute("""
                    INSERT OR REPLACE INTO potential_cache (chara_id, vo, vi, da, li, sk)
                    VALUES (?,?,?,?,?,?)
                """, list(map(int, row)))
        potential.copy_card_data_from_master(update_all=True)

    def _write_potentials_csv(self):
        potentials = db.cachedb.execute_and_fetchall("SELECT * FROM potential_cache", out_dict=True)
        with storage.get_writer(PROFILE_PATH / "{}.ptl".format(self.profile), 'w') as fw:
            fw.write(",".join(keys) + "\n")
            for data in potentials:
                fw.write(",".join(map(str, data.values())) + "\n")

    def _initialize_custom_csv(self):
        if not (PROFILE_PATH / "{}.cst".format(self.profile)).exists():
            with storage.get_writer(PROFILE_PATH / "{}.cst".format(self.profile), 'w') as fw:
                fw.write("id,rarity,image_id,vocal,dance,visual,life,leader_skill_id,skill_type,condition,available_time_type,probability_type,value,value_2,value_3\n")

    def _load_custom(self):
        custom_card.initialize_custom_card_list()
        self._initialize_custom_csv()
        with storage.get_reader(PROFILE_PATH / "{}.cst".format(self.profile), 'r') as fr:
            csv_reader = csv.reader(fr)
            next(csv_reader)  # Skip headers
            for row in csv_reader:
                db.cachedb.execute("""
                    INSERT OR REPLACE INTO custom_card (id, rarity, image_id, vocal, dance, visual, life,
                                                         leader_skill_id, skill_type, condition, available_time_type,
                                                         probability_type, value, value_2, value_3)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, list(map(int, row)))
        custom_card.refresh_custom_card_images()

    def _write_custom_csv(self):
        custom_cards = db.cachedb.execute_and_fetchall("SELECT * FROM custom_card", out_dict=True)
        with storage.get_writer(PROFILE_PATH / "{}.cst".format(self.profile), 'w') as fw:
            fw.write(",".join(custom_keys) + "\n")
            for data in custom_cards:
                fw.write(",".join(map(str, data.values())) + "\n")

    def cleanup(self):
        self._write_custom_csv()
        self._write_potentials_csv()
        self._write_owned_cards()
        self._write_units()


pm = ProfileManager()


@atexit.register
def cleanup():
    pm.cleanup()
