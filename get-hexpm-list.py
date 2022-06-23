#!/usr/bin/env python3

import requests
import json
import sys
from pprint import pprint

fulllist = []
page = 1
while True:
    url = "https://hex.pm/api/packages?page=%u" % page
    print(url)
    r = requests.get(url)

    if r.status_code == 200:
        if r.json():
            data = r.json()
            fulllist.extend(data)
        else:
            break
    else:
        print("ERROR DOWNLOADING: %s" % url, file=sys.stderr)
        break

    page += 1
#    if page > 4:
#        break;

with open("hexpm.json", "w+t", encoding="utf-8") as f:
    json.dump(fulllist, f, indent=4)
