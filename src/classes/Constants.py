import pathlib
from dotenv import dotenv_values

ENV = dotenv_values()

###############
# Preferences #
###############
CREATE_CURRENT_ZIP = ENV["EXTRACTOR_CURRENT_ZIP"] == "true"
TESTING_BUILDS = ENV["EXTRACTOR_TESTING_BUILDS"] == "true"
EXTRACT_LAUNCHER = ENV["EXTRACTOR_LAUNCHER"] == "true"

IDA_ENABLED = ENV["EXTRACTOR_IDA_ENABLED"] == "true"
IDA_AUTH = ENV["EXTRACTOR_IDA_AUTH"]
IDA_SERVER = ENV["EXTRACTOR_IDA_SERVER"]
IDA_CMD = ENV["EXTRACTOR_IDA_CMD"]
IDA_WORKDIR = pathlib.Path(ENV["EXTRACTOR_IDA_WORKDIR"])

#############
# URL Hosts #
#############
ROTMG_URLS = {
    "Production": "https://realmofthemadgod.appspot.com"
}

if TESTING_BUILDS:
    ROTMG_URLS["Testing"]  =  "https://rotmgtesting.appspot.com"
    ROTMG_URLS["Testing2"] =  "https://realmtesting2.appspot.com"
    ROTMG_URLS["Testing3"] =  "https://rotmgtesting3.appspot.com"
    ROTMG_URLS["Testing4"] =  "https://rotmgtesting4.appspot.com"
    ROTMG_URLS["Testing5"] =  "https://rotmgtesting5.appspot.com"


WEBSERVER_URL = ENV["HTTP"] + ENV["EXTRACTOR_URL"]

# add webhook url + role id to send a discord message when a new Client build is released
DISCORD_WEBHOOK_URL = ENV["EXTRACTOR_WEBHOOK_URL"]
DISCORD_WEBHOOK_MESSAGE = ENV["EXTRACTOR_WEBHOOK_MESSAGE"]

#############
# URL Paths #
#############
APP_INIT_PATH = "/app/init?platform=standalonewindows64&key=9KnJFxtTvLu2frXv"


##############
# File Paths #
##############

# ./src
SRC_DIR = pathlib.Path(__file__).parent.parent

# ./ - repository root
ROOT_DIR = SRC_DIR.parent

# ./output - all files, including temp outputted by the program
OUTPUT_DIR = ROOT_DIR / "output"

# ./output/publish - published outputs visible on the web server
PUBLISH_DIR = OUTPUT_DIR / "publish"

# ./output/temp - temporary directory cleared everytime the program is run
TEMP_DIR = OUTPUT_DIR / "temp"

# ./output/temp/files - temporary file download location
FILES_DIR = TEMP_DIR / "files"

# ./output/temp/work - temporary location to generate output before being copied to web/repo
WORK_DIR = TEMP_DIR / "work"

############
# Binaries #
############

BINARIES_DIR = SRC_DIR / "binaries"

LAUNCHER_UNPACKER_WINDOWS = BINARIES_DIR / "launcher_unpacker" / "unpacker-win.exe"
LAUNCHER_UNPACKER_LINUX = BINARIES_DIR / "launcher_unpacker" / "unpacker-linux"

IL2CPP_DUMPER_WINDOWS = BINARIES_DIR / "Il2CppInspector" / "Il2CppInspector-cli-win.exe"
IL2CPP_DUMPER_LINUX = BINARIES_DIR / "Il2CppInspector" / "Il2CppInspector-linux"