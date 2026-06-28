# Restore: rename bjensen back to barbara after test 08
# Run with: bash ch3-test-08-restore.sh
# Verify with:
#   ldapsearch -x -y ~/.ldappasswd "(uid=barbara)" uid
ldapmodrdn -x -y ~/.ldappasswd -r "uid=bjensen,ou=users,dc=marsel,dc=is" "uid=barbara"
