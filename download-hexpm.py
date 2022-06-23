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

VERSION = "0.0.0"

# ----------------------------------------------------------------------------------------------------------------------
#   Imports
# ----------------------------------------------------------------------------------------------------------------------

import sys
import argparse
import time
import requests
import json
import os
import multiprocessing

# ----------------------------------------------------------------------------------------------------------------------
#   Functions
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
#   Function: error
#
#   Prints an error and quits program
# ----------------------------------------------------------------------------------------------------------------------
def error(message: str):
    print("Error: %s", file=sys.stderr)
    exit(1)


# ----------------------------------------------------------------------------------------------------------------------
#   Function: get_full_repo_data
#
#   Returns a list of dictionary items containing the full json of the repo list
# ----------------------------------------------------------------------------------------------------------------------
def get_full_repo_data() -> list[dict]:
    full_list = []
    page = 1
    print("Downloading metadata ", end="")
    while True:
        url = "https://hex.pm/api/packages?page=%u" % page
        print(".", end="")
        r = requests.get(url)

        if r.status_code == 200:
            if r.json():
                data = r.json()
                full_list.extend(data)
            else:
                break
        else:
            error("Unable to download %s" % url)

        page += 1

    print("")
    return full_list


# ----------------------------------------------------------------------------------------------------------------------
#   Function: save_repo_json
#
#   Gets the full json of the repo from hex.pm and saves it as hexpm.json
# ----------------------------------------------------------------------------------------------------------------------
def save_repo_json():
    repo_data = get_full_repo_data()
    filename = "hexpm.json"
    with open(filename, "w+t", encoding="utf-8") as f:
        json.dump(repo_data, f, indent=4)
    print("Saved repo list as %s" % filename)
    print("This will be used when running download if it exists")


# ----------------------------------------------------------------------------------------------------------------------
#   Function: get_repo_json
#
#   If hexpm.json exists then this reads and returns the parsed data. Otherwise it gets the full json from web at hex.pm
# ----------------------------------------------------------------------------------------------------------------------
def get_repo_json() -> list[dict]:
    filename = "hexpm.json"
    if os.path.isfile(filename):
        with open(filename, "rt") as f:
            full_list = json.load(f)
    else:
        full_list = get_full_repo_data()

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
def determine_files_to_download(full_list: list, download_dir: str) -> list[tuple]:
    files_to_download = []
    for package in full_list:
        name = package["name"]

        package_url = "https://repo.hex.pm/packages/%s" % name
        local_package_file = os.path.join(download_dir, "packages", name)
        include_package = False

        for release in package["releases"]:
            version = release["version"]
            tarball_url = "https://repo.hex.pm/tarballs/%s-%s.tar" % (name, version)
            local_file = os.path.join(download_dir, "tarballs", "%s-%s.tar" % (name, version))
            if not os.path.isfile( local_file ):
                files_to_download.append( (tarball_url,local_file) )
                include_package = True

        if include_package or not os.path.isfile(local_package_file ):
                files_to_download.append( (package_url,local_package_file) )

    return files_to_download

# ----------------------------------------------------------------------------------------------------------------------
#   Function: get_total_count_of_files
#
#   Takes the complete json of the repo and counts the total number of files in the repo
# ----------------------------------------------------------------------------------------------------------------------
def get_total_count_of_files(full_list: list) -> int:
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
def download_file(index_total_url_and_file:tuple):
    (index,total,url,filepath) = index_total_url_and_file
    r = requests.get(url)
    if r.status_code == 200:
        try:
            with open(filepath, "w+b") as f:
                f.write(r.content)
                print( "Downloaded [%u/%u]: %s" % (index,total,url))
        except:
            print( "Removing partially saved file: %s" % filepath)
            os.remove( filepath )

# ----------------------------------------------------------------------------------------------------------------------
#   Function: download_files_in_parallel
#
#   Takes a list of tuples of format ( URL, FILEPATH ) and downloads each one using parallel threads for higher
#   throughput
# ----------------------------------------------------------------------------------------------------------------------
def download_files_in_parallel(urls_and_files:list[tuple]):
    totalfiles = len(urls_and_files)
    index_total_url_and_file = []
    index = 0
    for (url,file) in urls_and_files:
        index += 1
        index_total_url_and_file.append( (index,totalfiles,url,file) )
    with multiprocessing.Pool(100) as p:
        p.map(download_file, index_total_url_and_file, 1)

# ----------------------------------------------------------------------------------------------------------------------
#   Function: main
#
#   Main function
# ----------------------------------------------------------------------------------------------------------------------
def main(argv: list) -> int:
    global g_num_files_to_download

    parser = argparse.ArgumentParser(description="Downloads a mirror of repo.hex.pm")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("command", choices=["download", "list"], help="Command to use")
    args = parser.parse_args(argv)

    if args.command == "list":
        save_repo_json()
    elif args.command == "download":
        full_list = get_repo_json()
        total_repo_files = get_total_count_of_files(full_list)
        download_list = determine_files_to_download(full_list, "repo.hex.pm")
        g_num_files_to_download = len(download_list)
        print( "Downloading %u new files from repo.hex.pm (from total of %u)" % (g_num_files_to_download,total_repo_files))
        download_files_in_parallel( download_list )

# ----------------------------------------------------------------------------------------------------------------------
#   Entry Point
# ----------------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    ret_code = main(sys.argv[1:])
    exit(ret_code)
