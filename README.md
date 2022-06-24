download-hexpm
==============

A single file Python script for downloading the elixir repository from repo.hex.pm for use with an offline mirror.

All that is required to run a mirror is to have a clone of https://repo.hex.pm. Ideally there would be an rsync
service that allowed someone to mirror it that way. Unfortunately there is not, nort is directory indexing enabled
on the repo.hex.pm site. 

This script uses the API at https://hex.pm/api/packages?page=X to determine the list of packages stored on repo.hex.pm
and determines their URLs.

The simpliest use is

    ./download-hex.pm download

By default this will download to a directory `./repo.hex.pm`.

Once this has been downloaded it can be updating at a later stage by running the same command again. This will only download
new files.

To make the download fast, by default this will run 100 download jobs in parallel. This can be controlled using `--num-jobs`

Running a mirror
----------------

The best way to run a mirror on an offline network is to host a webserver serving the files from the download directory as
https://repo.hex.pm

In order allow hex to accept the TLS certificate either set enviroment variable `HEX_CACERTS_PATH` to a PEM file containing
your root CA. Or configure hex with `mix hex.config cacerts_path`

Alternatively it can be served on a different address and just use HTTP. In which case set `HEX_MIRROR` to point to the server.
Or configure hex with `mix hex.config mirror_url`

To test on local computer you can use

    python3 -m http.server ./repo.hex.pm 8000

Then set environment variable

    HEX_MIRROR = http://localhost:8000

Version
-------

1.0.0 - June 2022

This is an operational version. Note however there is very little error handling and may fail badly if things don't go
as expected.

License
-------

This is free and unencumbered software released into the public domain.

Released into the Public Domain by dual licensing with UNLICENSE and CC0

June 2022
