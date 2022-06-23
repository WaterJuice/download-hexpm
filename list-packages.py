#!/usr/bin/env python3

import json
import sys
from pprint import pprint


def download_package(package: dict):
    name = package["name"]
    # print( "Processing: %s" % name)
    package_url = "https://repo.hex.pm/packages/%s" % name
    local_file = "repo.hex.pm/packages/%s" % name
    command = "curl -# -C - -o %s %s &" % (local_file, package_url)
    print(command)
    # print( package_url )
    for release in package["releases"]:
        version = release["version"]
        #        print( "version: %s" % version )
        tarball_url = "https://repo.hex.pm/tarballs/%s-%s.tar" % (name, version)
        local_file = "repo.hex.pm/tarballs/%s-%s.tar" % (name, version)
        #        print( tarball_url )
        #        url = release["url"]
        command = "curl -# -C - -o %s %s &" % (local_file, tarball_url)
        print(command)

    command = "wait $(pgrep curl)"
    print(command)


with open("hexpm.json", "rt") as f:
    data = json.load(f)

print("#!/bin/bash -ex")

for package in data:

    #    print (package["name"])
    download_package(package)
