import shutil
import math
import requests
from datetime import datetime
from time import sleep

from classes import AppSettings
from classes import logger
from classes import Constants
from functions import *


def full_build_extract(prod_name, build_name, app_settings):
    files_dir: Path     = Constants.FILES_DIR   / prod_name.lower() / build_name.lower()    # ./output/temp/files/production/client
    work_dir: Path      = Constants.WORK_DIR    / prod_name.lower() / build_name.lower()    # ./output/temp/work/production/client
    publish_dir: Path   = Constants.PUBLISH_DIR / prod_name.lower() / build_name.lower()    # ./output/publish/production/client

    log_file = work_dir / "log.txt"
    logger.setFileLog(log_file)
    logger.printTime()

    logger.log(logging.INFO, f"Starting {prod_name} {build_name}")
    IndentFilter.level += 1

    pre_setup = pre_build_setup(prod_name, build_name, app_settings, work_dir, publish_dir)
    if not pre_setup:
        return False

    build_files_dir = download_archive_build(prod_name, build_name, app_settings, files_dir, work_dir, archive=False)
    if not build_files_dir:
        return False

    extracted = extract_build(build_name, build_files_dir, work_dir)
    if not extracted:
        return False

    output_build(prod_name, build_name, app_settings, work_dir, publish_dir, extracted[0])

    logger.log(logging.INFO, f"Done {prod_name} {build_name}")
    IndentFilter.level -= 1


def pre_build_setup(prod_name, build_name, app_settings, work_dir, publish_dir):
    """
    * Assert that their is a build to download
    * Compare build hashes (test if there is a new build out)
    * Write some app_settings info (build_hash, etc)
    """

    if not app_settings["build_hash"]:
        logger.log(logging.WARNING, f"{prod_name} does not have a {build_name} build available, aborting.")
        IndentFilter.level -= 1
        return False

    # Compare build hashes
    build_hash_file = publish_dir / "current" / "build_hash.txt"
    if build_hash_file.is_file():
        current_build_hash = read_file(build_hash_file)
        if current_build_hash == app_settings["build_hash"]:
            logger.log(logging.INFO, f"Current build hash is equal, aborting.")
            IndentFilter.level -= 1
            return False

    logger.log(logging.INFO, f"New build! Build hash: {app_settings['build_hash']}")
    write_file(work_dir / "build_hash.txt", app_settings["build_hash"], overwrite=True)
    write_file(work_dir / "build_version.txt", app_settings["build_version"], overwrite=True)
    return True


def download_archive_build(prod_name, build_name, app_settings, files_dir, work_dir, download=True, archive=True):
    """
    * Downloads all files for the current build.
    * Launcher assets are automatically unpacked.
    * Archives all the build files to a .zip in their original state.
    """

    build_url = app_settings["build_cdn"] + app_settings["build_hash"] + "/" + app_settings["build_id"]
    logger.log(logging.INFO, f"Build URL is {build_url}")

    # Download build files, output directory can change depending 
    # if it's the client vs how the launcher exe is unpacked 
    build_files_dir = None

    if download:
        if build_name == "Client":
            build_files_dir = download_client_assets(build_url, files_dir)
        elif build_name == "Launcher":
            build_files_dir = download_launcher_assets(build_url, app_settings["build_id"], files_dir)

    if build_files_dir is None:
        logger.log(logging.ERROR, f"Failed to download/extract {prod_name} {build_name} assets! Aborting")
        return False
    
    archive_build_files(build_files_dir, work_dir, archive)
    return build_files_dir


def extract_build(build_name, build_files_dir, work_dir):
    """
    * Extracts all Unity assets using UnityPy.
    * Attempts to extract the current Exalt Version from il2cpp metadata.
    * Merges xml files (objects/tiles), for client builds.
    * Dumps Il2Cpp using  Il2CppInspector.
    Returns the Exalt Version (for client) or "" for launcher.
    """

    extracted_assets_dir = work_dir / "extracted_assets"
    extract_unity_assets(build_files_dir, extracted_assets_dir)

    exalt_version = ""
    if build_name == "Client":
        # Extract exalt version (e.g. 1.3.2.1.0)
        metadata_file = build_files_dir / "RotMG Exalt_Data" / "il2cpp_data" / "Metadata" / "global-metadata.dat"
        exalt_version = extract_exalt_version(metadata_file, work_dir / "exalt_version.txt")

        merge_xml_files(extracted_assets_dir / "TextAsset" / "manifest.json", extracted_assets_dir, work_dir)

    # Dump il2cpp using Il2CppInspector
    data_dir = find_path(build_files_dir, "*_Data")
    metadata = data_dir / "il2cpp_data" / "Metadata" / "global-metadata.dat"
    gameassembly = build_files_dir / "GameAssembly.dll"
    dump_output = work_dir / "il2cpp_dump"
    dump_il2cpp(gameassembly, metadata, dump_output)
    
    run_ida_script(gameassembly, work_dir)

    return (exalt_version,)


def output_build(prod_name, build_name, app_settings: AppSettings, work_dir: Path, publish_dir: Path, exalt_version=""):
    """
    Performs the final steps for outputting a build after archival/extraction.
    * Writes the current timestamp.txt
    * Copies the output files to the published dir
    """

    logger.log(logging.INFO, "Outputting build...")
    IndentFilter.level += 1

    timestamp = math.floor(datetime.now().timestamp())
    write_file(work_dir / "timestamp.txt", str(timestamp))

    logger.log(logging.INFO, f"Copying output files...")

    publish_dir_buildhash: Path = publish_dir / app_settings["build_hash"]
    publish_dir_current: Path = publish_dir / "current"

    if build_name == "Client" and exalt_version != "":
        publish_dir_buildhash = publish_dir / f"{exalt_version} - {app_settings['build_hash']}"

    # calculate diff for webhook
    diff = None
    if Constants.DISCORD_WEBHOOK_URL != "" and publish_dir_current.exists():
        diff = diff_directories(work_dir / "extracted_assets", publish_dir_current / "extracted_assets")

    # Delete and copy files to /output/{build_hash}
    if publish_dir_buildhash.exists():
        logger.log(logging.INFO, f"Deleting {publish_dir_buildhash}")
        shutil.rmtree(publish_dir_buildhash)

    logger.log(logging.INFO, f"Copying files to {publish_dir_buildhash}")
    shutil.copytree(work_dir, publish_dir_buildhash)

    # Delete and copy files to /output/current
    if publish_dir_current.exists():
        logger.log(logging.INFO, f"Deleting {publish_dir_current}")
        shutil.rmtree(publish_dir_current)

    logger.log(logging.INFO, f"Copying files to {publish_dir_current}")
    shutil.copytree(work_dir, publish_dir_current)

    # Create current.zip
    if Constants.CREATE_CURRENT_ZIP:
        logger.log(logging.INFO, f"Creating current.zip")
        current_zip = publish_dir / "current.zip"
        if current_zip.exists():
            current_zip.unlink()

        shutil.make_archive(
            base_name=publish_dir / "current",
            format="zip",
            root_dir=publish_dir_current
        )

    # send webhook, after all files have been copied
    if diff and build_name == "Client":
        logger.log(logging.INFO, "Sending discord webhook")

        url = f"{Constants.WEBSERVER_URL}/" + str(publish_dir_buildhash.relative_to(Constants.PUBLISH_DIR)) + "/"
        url = url.replace("\\", "/")

        webhook_json =  {
            "content": Constants.DISCORD_WEBHOOK_MESSAGE,
            "embeds": [
                {
                    "color": None,
                    "fields": [
                        { "name": "Enviornment", "value": prod_name.title(), "inline": True },
                        { "name": "Type", "value": build_name.title(), "inline": True },
                        { "name": "Exalt Version", "value": f"**{exalt_version}**", "inline": True },
                        {
                            "name": "Download",
                            "value": f"```bash\nwget --recursive -np -nH --cut-dirs=2 --reject=\"index.html*\" \"{url}\"\n```"
                        },
                        { "name": "Diff Count (extracted assets only)", "value": f"```diff\nfiles: +{diff[0]} -{diff[1]}\nlines: +{diff[2]} -{diff[3]}\n```" }
                    ]
                }
            ]
        }

        requests.post(Constants.DISCORD_WEBHOOK_URL, json=webhook_json)

    sleep(2)

    logger.log(logging.INFO, f"Done!")
    IndentFilter.level -= 1
    return True


def main():

    # Delete previous contents of ./temp/
    shutil.rmtree(Constants.TEMP_DIR, ignore_errors=True)
    sleep(5) # Wait for filesystem to catch up / prevent bugs

    # Setup logger
    logger.setup()
    
    prod_names = Constants.ROTMG_URLS.keys()
    for prod_name in prod_names:
        app_settings = AppSettings(Constants.ROTMG_URLS[prod_name])
        full_build_extract(prod_name, "Client", app_settings.client)

        if Constants.EXTRACT_LAUNCHER:
            full_build_extract(prod_name, "Launcher", app_settings.launcher)

    logger.log(logging.INFO, "Done!")

    # loop the main function to continuously check for new builds 
    loop_time = 10 # minutes
    logger.log(logging.INFO, f"Looping in {loop_time} minutes...\n\n")
    sleep(loop_time * 60)
    main()


if __name__ == "__main__":

    main()
