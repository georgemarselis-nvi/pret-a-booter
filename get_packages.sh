#!/usr/bin/env bash

/usr/bin/dnf repoquery --installed --qf '%{name}' > packages.txt
