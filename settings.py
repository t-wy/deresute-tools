from chihiro import ROOT_DIR
import platform

LOGGER_NAME = "chihiro"
LOG_DIR = ROOT_DIR / "logs"
MAX_WORKERS = 6  # Set this high and your PC dies

DATA_PATH = ROOT_DIR / "data"
BACKUP_PATH = DATA_PATH / "backup"
DB_PATH = DATA_PATH / "db"
IMAGE_PATH = DATA_PATH / "img"
IMAGE_PATH32 = DATA_PATH / "img32"
IMAGE_PATH64 = DATA_PATH / "img64"
ZIP_PATH = ROOT_DIR / "img.zip"
MUSICSCORES_PATH = DATA_PATH / "musicscores"
CACHEDB_PATH = DB_PATH / "chihiro.db"
MANIFEST_PATH = DB_PATH / "manifest.db"
MASTERDB_PATH = DB_PATH / "master.db"

PROFILE_PATH = DATA_PATH / "profiles"

STATIC_PATH = ROOT_DIR
TOOL_EXE = STATIC_PATH / "tool.exe"
if platform.system() == "Darwin": # Mac
    TOOL_EXE = STATIC_PATH / "tool_mac"
elif platform.system() == "Linux": # Mac
    TOOL_EXE = STATIC_PATH / "tool_linux"

TEMP_PATH = STATIC_PATH / "temppp"

RHYTHM_ICONS_PATH = ROOT_DIR / "img"
MY_IMAGE_PATH = RHYTHM_ICONS_PATH / "my"

INDEX_PATH = DATA_PATH / "index"

ABUSE_CHARTS_PATH = ROOT_DIR / "abuse"
CHART_PICS_PATH = ROOT_DIR / "charts"

REMOTE_CACHE_SCORES_URL = "https://raw.githubusercontent.com/oayimikagakat/chihiro-static/master/live_detail_cache.csv"
REMOTE_TRANSLATED_SONG_URL = "https://raw.githubusercontent.com/oayimikagakat/chihiro-static/master/translated.csv"