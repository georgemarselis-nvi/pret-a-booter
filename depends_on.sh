#!/usr/bin/env bsh

/usr/bin/dnf repoquery --requires --resolve $1
