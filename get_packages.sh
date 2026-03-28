#!/usr/bin/env bash

/usr/bin/dnf repoquery --installed --qf '%{name}\n' > packages.txt
