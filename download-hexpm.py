#!/usr/bin/env python3 -u
# ----------------------------------------------------------------------------------------------------------------------
#  download-hexpm.py
#  -----------------
#
#   This creates a mirror of repo.hex.pm
#   It will use the API on hex.pm to get a list of all packages, then download all packages that are missing locally
#   in directory repo.hex.pm.
#   This directory can then be served as a website to act as a mirror.
#
#   Author: waterjuice.org
#
#   Unlicense: This is free and unencumbered software released into the public domain.
#
#   Version History
#   ---------------
#   Jun 2022 - Created
# ----------------------------------------------------------------------------------------------------------------------

VERSION = "1.0.0"

# ----------------------------------------------------------------------------------------------------------------------
#   Imports
# ----------------------------------------------------------------------------------------------------------------------

import argparse
import csv
import hashlib
import multiprocessing
import os
import requests
import sys
import time

# ----------------------------------------------------------------------------------------------------------------------
#   Constants
# ----------------------------------------------------------------------------------------------------------------------

# This is the default number of parallel jobs to download from repo.hex.pm. This can be changed using --num-jobs
DEFAULT_DOWNLOAD_JOBS = 100
# This is the number of parallel jobs to download from hex.pm for the index. This server is rate limited so setting
# this too high will slow things down.
API_PULL_JOBS = 25

# ----------------------------------------------------------------------------------------------------------------------
#   Functions
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
#   Function: error
#
#   Prints an error and quits program
# ----------------------------------------------------------------------------------------------------------------------
def error(message: str) -> None:
    print("Error: %s" % message, file=sys.stderr)
    exit(1)


# ----------------------------------------------------------------------------------------------------------------------
#   Function: download_package_page
#
#   Downloads a packages page and returns json data as list. Empty list if page does not exist
# ----------------------------------------------------------------------------------------------------------------------
def download_package_page(page: int) -> list[dict]:
    url = "https://hex.pm/api/packages?page=%u" % page
    code = 429
    page_data: list[dict] = []
    while code == 429:
        r = requests.get(url)
        code = r.status_code
        if code == 200:
            page_data = r.json()
        if code == 429:
            # Rate limited. So pause a second and try again.
            time.sleep(1)

    if code != 200:
        error("Unable to access url: %s (Error: %u)" % (url, code))
    return page_data


# ----------------------------------------------------------------------------------------------------------------------
#   Function: get_full_repo_data
#
#   Returns a list of dictionary items containing the full json of the repo list
# ----------------------------------------------------------------------------------------------------------------------
def get_full_repo_data() -> list[dict]:
    full_list = []
    print("Downloading package list: ", end="")
    last_page = False
    page_block_index = 1
    with multiprocessing.Pool(API_PULL_JOBS) as process_multitasker:
        while not last_page:
            page_indexes = range(page_block_index, page_block_index + API_PULL_JOBS)
            print(".", end="")
            pages = process_multitasker.map(download_package_page, page_indexes, 1)
            for data in pages:
                if data:
                    full_list.extend(data)
                else:
                    # Reached blank page
                    last_page = True
            page_block_index += API_PULL_JOBS
    print("")

    return full_list


# ----------------------------------------------------------------------------------------------------------------------
#   Function: determine_files_to_download
#
#   Takes the complete json of the repo and determines every file that needs to be downloaded and then checks if they
#   already are downloaded. The list returned contains files that need to be downloaded.
#   Note if there are any tarballs in a package that need downloading the package file itself is included for redownload
#   This returns of list of tuples of format
#   ( URL, FILEPATH )
# ----------------------------------------------------------------------------------------------------------------------
def determine_files_to_download(full_list: list[dict], download_dir: str) -> list[tuple[str, str]]:
    files_to_download: list[tuple[str, str]] = []
    for package in full_list:
        name = package["name"]

        package_url = "https://repo.hex.pm/packages/%s" % name
        local_package_file = os.path.join(download_dir, "packages", name)
        include_package = False

        for release in package["releases"]:
            version = release["version"]
            tarball_url = "https://repo.hex.pm/tarballs/%s-%s.tar" % (name, version)
            local_file = os.path.join(download_dir, "tarballs", "%s-%s.tar" % (name, version))
            if not os.path.isfile(local_file):
                files_to_download.append((tarball_url, local_file))
                include_package = True

        if include_package or not os.path.isfile(local_package_file):
            files_to_download.append((package_url, local_package_file))

    return files_to_download


# ----------------------------------------------------------------------------------------------------------------------
#   Function: get_total_count_of_files
#
#   Takes the complete json of the repo and counts the total number of files in the repo
# ----------------------------------------------------------------------------------------------------------------------
def get_total_count_of_files(full_list: list[dict]) -> int:
    num_files = 0
    for package in full_list:
        num_files += 1
        for release in package["releases"]:
            num_files += 1
    return num_files


# ----------------------------------------------------------------------------------------------------------------------
#   Function: download_file
#
#   Downloads a file from a URL and saves it to specified location. File only saved if full file downloaded.
#   This will replace any existing file
# ----------------------------------------------------------------------------------------------------------------------
def download_file(index_total_url_and_file: tuple[int, int, str, str]) -> None:
    (index, total, url, filepath) = index_total_url_and_file
    r = requests.get(url)
    if r.status_code == 200:
        try:
            with open(filepath, "w+b") as f:
                f.write(r.content)
                print("Downloaded [%u/%u]: %s" % (index, total, url))
        except:
            print("Removing partially saved file: %s" % filepath)
            os.remove(filepath)
    else:
        print("Failed to download: %s" % url)


# ----------------------------------------------------------------------------------------------------------------------
#   Function: ensure_folders_exist
#
#   Takes a list of tuples of format ( URL, FILEPATH ) and makes sure the folders for FILEPATH exist. If they don't
#   they will be created
# ----------------------------------------------------------------------------------------------------------------------
def ensure_folders_exist(urls_and_files: list[tuple[str, str]]) -> None:
    unique_dirs: dict[str, bool] = {}
    for (url, filepath) in urls_and_files:
        dir = os.path.dirname(filepath)
        if dir not in unique_dirs:
            os.makedirs(dir, exist_ok=True)
            unique_dirs[dir] = True


# ----------------------------------------------------------------------------------------------------------------------
#   Function: download_files_in_parallel
#
#   Takes a list of tuples of format ( URL, FILEPATH ) and downloads each one using parallel threads for higher
#   throughput
# ----------------------------------------------------------------------------------------------------------------------
def download_files_in_parallel(urls_and_files: list[tuple[str, str]], num_download_jobs: int) -> None:
    totalfiles = len(urls_and_files)
    ensure_folders_exist(urls_and_files)
    index_total_url_and_file: list[tuple[int, int, str, str]] = []
    index = 0
    for (url, file) in urls_and_files:
        index += 1
        index_total_url_and_file.append((index, totalfiles, url, file))
    with multiprocessing.Pool(num_download_jobs) as p:
        p.map(download_file, index_total_url_and_file, 1)


# ----------------------------------------------------------------------------------------------------------------------
#   Function: file_with_hash_exists
#
#   Determines if the specified file exists and has the correct hash. Returns True if file exists and has specified
#   sha512 hash. Note the sha512 hash is specified by string
# ----------------------------------------------------------------------------------------------------------------------
def file_with_hash_exists(filepath: str, hash: str) -> bool:
    if os.path.isfile(filepath):
        with open(filepath, "rb") as f:
            filehash = hashlib.sha512(f.read()).hexdigest()
            if filehash == hash:
                return True
    return False


# ----------------------------------------------------------------------------------------------------------------------
#   Function: download_and_process_hex_csv
#
#   Downloads the csv file specifed at repo.hex.pm/installs/ and processes it to get a list of all the version files
#   needed. This can process hex, rebar, and rebar3.
#   This returns of list of tuples of format
#   ( URL, FILEPATH )
# ----------------------------------------------------------------------------------------------------------------------
def download_and_process_hex_csv(
    download_dir: str, csv_file: str, file_prefix: str, file_suffix: str
) -> list[tuple[str, str]]:

    url = "https://repo.hex.pm/installs/%s" % csv_file
    r = requests.get(url)
    data = list(csv.DictReader(r.text.split("\n"), fieldnames=["hex_ver", "hash", "elixir_ver"]))
    # Generate list of files to download
    files_to_download = []

    # There are some repeated entries in the csv with the same elixir/hex version but different hash. So collect
    # all hashes so we can check our file against any of them
    unique_filepaths = {}
    for row in data:
        (elixir_ver, hex_ver, hash) = (row["elixir_ver"], row["hex_ver"], row["hash"])
        url = "https://repo.hex.pm/installs/%s/%s-%s%s" % (elixir_ver, file_prefix, hex_ver, file_suffix)
        file = os.path.join(download_dir, "installs", elixir_ver, "%s-%s%s" % (file_prefix, hex_ver, file_suffix))

        if file not in unique_filepaths:
            unique_filepaths[file] = {"filepath": file, "url": url, "hashes": []}
        unique_filepaths[file]["hashes"].append(hash)

    # Now process the unique files/urls and see if we have them downloaded already
    for file in unique_filepaths:
        url = unique_filepaths[file]["url"]
        match = False
        for hash in unique_filepaths[file]["hashes"]:
            # See if we have this file already downloaded
            if file_with_hash_exists(file, hash):
                match = True
        if not match:
            files_to_download.append((url, file))

    return files_to_download


# ----------------------------------------------------------------------------------------------------------------------
#   Function: get_extra_files_list
#
#   This creates a list of all the files that need to be downloaded from the installs directory and some from root dir.
#   Most of the files are checked if they exist and their hash matches. There are a few extra files that will always
#   be added. They are small files.
#   This returns of list of tuples of format
#   ( URL, FILEPATH )
# ----------------------------------------------------------------------------------------------------------------------
def get_extra_files_list(download_dir: str) -> list[tuple[str, str]]:
    files_to_download: list[tuple[str, str]] = []
    files_to_download += download_and_process_hex_csv(download_dir, "hex-1.x.csv", "hex", ".ez")
    files_to_download += download_and_process_hex_csv(download_dir, "rebar-1.x.csv", "rebar", "")
    files_to_download += download_and_process_hex_csv(download_dir, "rebar3-1.x.csv", "rebar3", "")
    # Add in other needed files
    extra_files = [
        "names",
        "versions",
        "installs/hex-1.x.csv",
        "installs/hex-1.x.csv.signed",
        "installs/rebar-1.x.csv",
        "installs/rebar-1.x.csv.signed",
        "installs/rebar3-1.x.csv",
        "installs/rebar3-1.x.csv.signed",
        "installs/public_keys.html",
    ]
    for extra in extra_files:
        filepath = os.path.join(download_dir, extra)
        url = "https://repo.hex.pm/%s" % extra
        files_to_download.append((url, filepath))

    return files_to_download


# ----------------------------------------------------------------------------------------------------------------------
#   Function: main
#
#   Main function
# ----------------------------------------------------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Downloads a mirror of repo.hex.pm. Use 'download-hexpm.py download' to download to ./repo.hex.pm"
    )
    parser.add_argument("--version", action="version", version="download-hexpm version " + VERSION)
    parser.add_argument("command", choices=["download"], help="Command to use")
    parser.add_argument(
        "--num-jobs",
        "-n",
        type=int,
        default=DEFAULT_DOWNLOAD_JOBS,
        help="Number of parallel download tasks. (Default %u)" % DEFAULT_DOWNLOAD_JOBS,
    )
    parser.add_argument("--dir", "-d", default="./repo.hex.pm", help="Download directory (Default ./repo.hex.pm)")
    args = parser.parse_args(argv)

    num_jobs = args.num_jobs
    download_dir = args.dir

    print("download-hexpm version " + VERSION)

    if args.command == "download":
        extra_files_list = get_extra_files_list(download_dir)
        full_list = get_full_repo_data()
        total_repo_files = get_total_count_of_files(full_list) + len(extra_files_list)
        download_list = determine_files_to_download(full_list, download_dir)

        download_list.extend(extra_files_list)
        print("Downloading %u files from repo.hex.pm (from total of %u)" % (len(download_list), total_repo_files))
        download_files_in_parallel(download_list, num_jobs)

    return 0


# ----------------------------------------------------------------------------------------------------------------------
#   Entry Point
# ----------------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    ret_code = main(sys.argv[1:])
    exit(ret_code)
