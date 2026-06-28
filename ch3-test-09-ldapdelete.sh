#!/bin/bash
# Test: ldapdelete on slapd 2.6.x
# Book: Packt OpenLDAP, page 128
# Delete matt from the directory
# Run with: bash ch3-test-09-ldapdelete.sh
# Verify with:
#   ldapsearch -x -y ~/.ldappasswd "(uid=matt)"
ldapdelete -x -y ~/.ldappasswd "uid=matt,ou=users,dc=marsel,dc=is"
ldapsearch -x -y ~/.ldappasswd "(uid=matt)"
