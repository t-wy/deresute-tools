from network.secrets import VIEWER_ID_KEY, SID_KEY

class ApiClient(object):
    def __init__(self, user, viewer_id, udid, app_ver, res_ver):
        self.user = user
        self.viewer_id = viewer_id
        self.udid = udid
        self.sid = None
        self.app_ver = app_ver
        self.res_ver = res_ver
        return

    def call(self, path, args):
        # ...
        return None