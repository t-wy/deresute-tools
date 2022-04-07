# rename this to tool.py and implement secrets.py, account.py and apiclient.py if needed
from network.account import viewer_id, user_id, udid
from network.api_client_tool import ApiClient
import json, re, requests
# cgss_tools_integration.py

def _base_query(query):
    query_url = ('https://starlight.kirara.ca/api/v1/{}').format(query)
    response = requests.get(query_url)
    return json.loads(response.content)


def get_truth_version():
    return _base_query('info')['truth_version']

def fail_safe(f):
    def wrapper(*args, **kwargs):
        try:
            res = f(*args, **kwargs)
        except:
            logger.info("Failed to run CGSS API")
            return
        return res
    return wrapper

def get_client():
    res = get_truth_version()
    response = requests.get('https://play.google.com/store/apps/details?id=jp.co.bandainamcoent.BNEI0242&hl=ja')
    content = response.content.decode('utf-8')
    idx = content.find(u'現在のバージョン')
    app_ver = re.search('\\d\\.\\d\\.\\d', content[idx:idx + 200]).group(0)
    client = ApiClient(user_id, viewer_id, udid, app_ver, res)
    return client

@fail_safe
def get_cards(game_id):
    game_id = int(game_id)
    client = get_client()
    data = client.call('/room/other', {'storage_diff_enabled': 1, 'before_refactor_flag': 2, 
       'other_viewer_id': game_id})
    results = [ item['room_item_id'] for idx, item in data['data']['item_list'].items() if item['room_item_id'] > 100000]
    return results


def get_song_ranking(live_detail_id, page):
    client = get_client()
    data = client.call('/live/get_live_detail_ranking', {'live_detail_id': live_detail_id, 'page': page})
    results = data['data']['rank_list']
    return results


@fail_safe
def get_top_build(live_detail_id, rank=1, player_id=None):
    client = get_client()
    if player_id is None:
        top_page = get_song_ranking(live_detail_id, (rank + 9) // 10)
        viewer_id = top_page[(rank + 9) % 10]['user_info']['viewer_id']
    else:
        viewer_id = int(player_id)
    data = client.call('/live/ranking_unit_member_list', {'live_detail_id': live_detail_id, 'friend_id': viewer_id, 
       'event_id': 0, 
       'get_effect_info': 0})
    results = data['data']
    return results
