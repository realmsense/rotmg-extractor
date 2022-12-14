import logging
import os
import json
import subprocess
import re as regex
import ntpath
import UnityPy
import requests
import shutil
from pathlib import Path
# from xml.etree import ElementTree

from classes import Constants
from classes import logger, IndentFilter
from functions.File import *


def extract_unity_assets(input_dir, output_path):

    file_patterns = [
        "^globalgamemanagers",
        "^level[0-9]",
        "^resources",
        "^sharedassets[0-9]"
    ]

    ignored_exts = [
        ".resS",
        ".resource"
    ]

    logger.log(logging.INFO, "Extracting build assets...")
    IndentFilter.level += 1

    # Get the _Data directory (where the unity files are located)
    data_dir = find_path(input_dir, "*_Data")

    # Iterate files
    for file_name in os.listdir(data_dir):
        file_path = os.path.join(data_dir, file_name)

        if not os.path.isfile(file_path):
            continue

        continue_loop = False

        for pattern in file_patterns:
            pattern = regex.compile(pattern)
            if pattern.search(file_name):
                continue_loop = True
                break

        for ext in ignored_exts:
            if file_name.endswith(ext):
                continue_loop = False
                break

        if not continue_loop:
            continue

        extract_assets(file_path, output_path)

    IndentFilter.level -= 1
    logger.log(logging.INFO, "Build assets extracted!")


def extract_assets(file_path, output_path):

    file_name = Path(file_path).name
    logger.log(logging.INFO, f"Extracting assets from \"{file_name}\"")
    IndentFilter.level += 1

    obj_type_len = 0  # 13
    obj_name_len = 0  # 35
    path_id_len = 0  # 6

    env = UnityPy.load(file_path)
    for obj in env.objects:

        obj_types = ["TextAsset", "Sprite", "Texture2D", "AudioClip", "MonoScript"]
        if obj.type not in obj_types:
            continue

        data = obj.read()
        output_file = ""

        obj_name = data.name
        if obj_name == "":
            obj_name = "Untitled"

        if obj.type == "TextAsset":
            first_line = data.text.partition("\n")[0]

            ext = "txt"
            if first_line.startswith("<!DOCTYPE html>"):
                ext = "html"
            elif first_line.startswith("<") or "xml" in first_line:
                ext = "xml"
            elif first_line.startswith("{") or first_line.startswith("["):
                ext = "json"

            output_file = output_path / str(obj.type) / f"{obj_name}.{ext}"
            write_file(output_file, data.m_Script, "wb")

        elif obj.type == "Sprite" or obj.type == "Texture2D":
            # print pathid or something like that here
            output_file = output_path / str(obj.type) / f"{obj_name}.png"
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)

            try:
                data.image.save(output_file)
            except Exception as e:
                logger.log(logging.ERROR, f"Error saving {str(obj.type)} \"{obj_name}\" (Path ID: {obj.path_id} in {file_name}) Error: {e}")

        elif obj.type == "AudioClip":
            for name, data in data.samples.items():
                output_file = output_path / str(obj.type) / name
                write_file(output_file, data, "wb")

        elif obj.type == "MonoScript":

            dirs = data.m_Namespace.split(".")
            dirs = [regex.sub('[*?:"<>|]', "", dir) for dir in dirs] # remove invalid file characters
            dir = "/".join(dirs)

            output_file = output_path / str(obj.type) / dir / f"{obj_name}.json"

            keys = ["m_AssemblyName", "m_Namespace", "m_ClassName", "name"]
            base = { key: data.__dict__[key] for key in keys}

            json_pretty = json.dumps(base, indent=4)

            write_file(output_file, json_pretty, "w")


        if output_file != "":

            # logger.log(logging.INFO, f"{str(obj.type)} {obj_name} {obj.path_id} {file_name}")
            # logger.log(logging.INFO, f"{str(obj.type):<13} {obj_name:<35} {obj.path_id:<6} {file_name}")

            if len(str(obj.type)) > obj_type_len:
                obj_type_len = len(str(obj.type)) + 1
            if len(obj_name) > obj_name_len:
                obj_name_len = len(obj_name) + 1
            if len(str(obj.path_id)) > path_id_len:
                path_id_len = len(str(obj.path_id)) + 2

            logger.log(logging.INFO, "{:<{}} {:<{}} {:<{}}".format(
                obj_name, obj_name_len,
                str(obj.type), obj_type_len,
                f"(Path ID: {obj.path_id})", path_id_len
            ))

    IndentFilter.level -= 1


def extract_exalt_version(metadata_file: Path, output_file: Path):
    """ Attempts to find the current version string (e.g. `1.3.2.0.0`) located in `global-metadata.dat` """

    # TODO: Decode/decrypt build version from appsettings

    # A simple regex to capture "1.3.2.0.0" isn't as simple as there are many
    # strings that match. However, the current exalt version is stored in the
    # client as a const string (so it appears in the metadata). It's located
    # in the static class KFFELHLKACG.AFOGMBOANMH.
    # Because it is stored in the metadata, we can use regex to match the
    # string using the previous const strings in the class to get the correct
    # one. (Which is 127.0.0.1 - see the class KFFELHLKACG)

    # For testing:
    # cat global-metadata.dat | grep --text -Po "127\.0\.0\.1[\x00-\x20]*(\d(?:\.\d){4})"

    logger.log(logging.INFO, "Attempting to extract Exalt version string")
    IndentFilter.level += 1

    pattern = regex.compile(b"127\.0\.0\.1[\x00-\x20]*(\d(?:\.\d){4})")

    version_string = ""
    with open(metadata_file, "rb") as file:
        data = file.read()
        result = pattern.findall(data)

        if len(result) == 1:
            version_string = result[0].decode("utf-8")
            logger.log(logging.INFO, f"Exalt version is \"{version_string}\"")
            write_file(output_file, version_string)
        else:
            logger.log(logging.INFO, "Could not extract version string! Must be manually updated.")
            write_file(output_file, "")

    IndentFilter.level -= 1
    return version_string


def merge_xml_files(manifest_file: Path, input_dir: Path, output_dir: Path):
    logger.log(logging.INFO, f"Merging xml files...")
    IndentFilter.level += 1

    if not manifest_file.exists():
        logger.log(logging.ERROR, f"Unable to find {manifest_file} !")
        IndentFilter.level -= 1
        return

    manifest = read_json(manifest_file)
    for output_file_name in manifest:
        xml_files = []
        file_names = []
        for merge_file in manifest[output_file_name]:
            if not isinstance(merge_file, dict):
                continue

            merge_file_path = merge_file.get("path")
            if not merge_file_path:
                continue

            file_name = ntpath.basename(merge_file_path)
            if not file_name.endswith("xml"):
                continue

            file_path = input_dir / "TextAsset" / file_name
            if not os.path.isfile(file_path):
                logger.log(logging.ERROR, f"Could not find {file_path} !")
                continue

            xml_files.append(file_path)
            file_names.append(file_name)

        if len(xml_files) == 0:
            continue

        logger.log(logging.DEBUG, f"Merging {len(xml_files)} files. {file_names}")
        merged = merge_xml(xml_files)

        output_file = output_dir / "xml" / f"{output_file_name}.xml"
        write_file(output_file, merged, overwrite=False)
        logger.log(logging.INFO, f"Successfully merged {len(file_names)} files into {output_file_name}.xml")

        # TODO: convert to json (see nrelay code)

    IndentFilter.level -= 1


def unpack_launcher_assets(launcher_path, output_path):

    unpacker_file = None
    if os.name == "nt":
        unpacker_file = Constants.LAUNCHER_UNPACKER_WINDOWS
    elif os.name == "posix":
        unpacker_file = Constants.LAUNCHER_UNPACKER_LINUX
    else:
        return

    logger.log(logging.INFO, "Unpacking launcher assets...")
    IndentFilter.level += 1

    process = subprocess.Popen(
        [unpacker_file, launcher_path, output_path],
        stdin=subprocess.PIPE, # bypass "Press any key to exit..."
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )

    logger.pipe(process.stdout)
    process.wait()

    logger.log(logging.INFO, "Done!")
    IndentFilter.level -= 1


def dump_il2cpp(gameassembly: Path, metadata_file: Path, output_dir: Path):

    dumper_file = None
    if os.name == "nt":
        dumper_file = Constants.IL2CPP_DUMPER_WINDOWS
    elif os.name == "posix":
        dumper_file = Constants.IL2CPP_DUMPER_LINUX
    else:
        return

    logger.log(logging.INFO, "Dumping il2cpp...")
    IndentFilter.level += 1

    output_dir.mkdir(parents=True, exist_ok=True)

    process = subprocess.Popen(
        [
            dumper_file, 
            "--bin", gameassembly, 
            "--metadata", metadata_file,
            "--layout", "class",
            "--select-outputs",
            "--py-out",   output_dir / "il2cpp.py",
            "--json-out", output_dir / "metadata.json",
            "--cs-out",   output_dir / "types",
            "--cpp-out",  output_dir / "cpp",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )

    logger.pipe(process.stdout)
    process.wait()

    logger.log(logging.INFO, "Done!")
    IndentFilter.level -= 1


def run_ida_script(gameassembly: Path, work_dir: Path):
    
    if not Constants.IDA_ENABLED:
        logger.log(logging.INFO, "Skipping IDA script")
        return

    logger.log(logging.INFO, "Generating IDA database and running script...")
    IndentFilter.level += 1

    # Copy gameassembly to ida workdir
    logger.log(logging.INFO, f"Copying {gameassembly} to {Constants.IDA_WORKDIR}")
    shutil.copy(gameassembly, Constants.IDA_WORKDIR)

    # TODO: modify IDA to run the Il2cppInspector script
    ida_command = f"ida.sh -c -A -Sanalysis.idc /root/ida/{gameassembly.name}"

    if Constants.IDA_SERVER != "" and Constants.IDA_SERVER is not None:
        logger.log(logging.INFO, f"Sending HTTP Request: {Constants.IDA_SERVER} {ida_command}")

        params = {
            "command": ida_command,
            "auth": Constants.IDA_AUTH,
        }

        res = requests.post(Constants.IDA_SERVER, params=params)
        logger.log(logging.INFO, f"IDA Server Response: {res.text}")

        i64_files = list(Constants.IDA_WORKDIR.glob("*.i64"))
        if len(i64_files) == 0:
            logger.log(logging.INFO, f"Could not find a generated *.i64 file! Aborting.")
            print(list(Constants.IDA_WORKDIR.glob("*")))
            return

        i64_file = i64_files[0]
        logger.log(logging.INFO, f"Copying {i64_file} to {work_dir}")
        shutil.copy(i64_files[0], work_dir)

        IndentFilter.level -= 1
        return

    # TODO: run IDA binary on local fs (windows)
    # Use Constants.IDA_CMD
    pass
