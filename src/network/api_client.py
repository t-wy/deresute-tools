import os
import subprocess
from ast import literal_eval

import customlogger as logger
from logic.card import Card
from settings import TOOL_EXE, TEMP_PATH


def remove_temp(f):
    def decorate(*args, **kwargs):
        res = f(*args, **kwargs)
        if not os.path.exists(TEMP_PATH):
            logger.info("Failed to run CGSS API")
        else:
            os.remove(TEMP_PATH)
        return res

    return decorate


@remove_temp
def _get_cards(game_id):
    subprocess.call(list(map(str, [TOOL_EXE, "card", game_id, TEMP_PATH])))
    if not os.path.exists(TEMP_PATH):
        return
    with open(TEMP_PATH) as fr:
        cards = fr.read().strip().split(",")
        return cards


def post_process(build):
    support = build['backmember_appeal']
    cards = [
        Card.from_id(_['card_id'], custom_pots=(
            _['potential_param_1'],
            _['potential_param_3'],
            _['potential_param_2'],
            _['potential_param_4'],
            _['potential_param_5']
        ))
        for _ in build['member_list']
    ]
    if len(build['supporter']) > 0:
        cards.append(
            Card.from_id(build['supporter']['card_id'], custom_pots=(
                build['supporter']['potential_param_1'],
                build['supporter']['potential_param_3'],
                build['supporter']['potential_param_2'],
                build['supporter']['potential_param_4'],
                build['supporter']['potential_param_5']
            ))
        )
    return cards, support

@remove_temp
def _get_top_build(live_detail_id, rank=1, player_id=None):
    if rank > 1:
        logger.info("Cannot get units other than #1 due to the absence of tool.py.")
    if id is not None:
        logger.info("Cannot get units other than #1 due to the absence of tool.py.")
    subprocess.call(list(map(str, [TOOL_EXE, "build", live_detail_id, TEMP_PATH])))
    if not os.path.exists(TEMP_PATH):
        return
    with open(TEMP_PATH) as fr:
        build = literal_eval(fr.read())
        return post_process(build)

try:
    from network.tool import get_cards as ___get_cards, get_top_build  as ___get_top_build
    get_cards = ___get_cards
    get_top_build = lambda live_detail_id, rank, player_id: post_process(___get_top_build(live_detail_id, rank, player_id))
except Exception:
    get_cards = _get_cards
    get_top_build = _get_top_build
