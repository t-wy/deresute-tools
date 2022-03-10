# tool.py (from tool.exe)
# please fill in the codes on your own
import customlogger as logger

def fail_safe(f):
    def wrapper(*args, **kwargs):
        try:
            res = f(*args, **kwargs)
        except:
            logger.info("Failed to run CGSS API")
            return
        return res
    return wrapper

@fail_safe
def get_cards(game_id):
    # /room/other
    return [100001]

def get_song_ranking(live_detail_id, page):
    # /live/get_live_detail_ranking
    return [{"rank":str(page * 10 + i),"score":"0","id":123456789,"name":"???"} for i in range(1, 11)]

@fail_safe
def get_top_build(live_detail_id, rank=1, player_id=None):
    # /live/ranking_unit_member_list
    dummy = lambda pos: {"position_id":pos,"card_id":100001,"level":90,"step":0,"love":600,"skill_level":10,"potential_param_1":0,"potential_param_2":0,"potential_param_3":0,"potential_param_4":0,"potential_param_5":0}
    return {"member_list":[dummy(pos) for pos in range(1, 6)],"supporter":dummy(0),"backmember_appeal":0,"effect_info":{"get_money":{"value":100,"type":2},"get_fan":{"value":10,"type":2}},"card_storage_list":[]}