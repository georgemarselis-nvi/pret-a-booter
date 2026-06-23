# slapd management
/usr/sbin/slaptest -v -f /etc/ldap/slapd.conf
/usr/sbin/slappasswd -s 12345
systemctl restart slapd
systemctl status slapd
# ldapsearch
# -y reads password from file (preferred, not visible in ps)
# -W prompts interactively
# -w 12345 password inline (visible in ps, avoid in production)
/usr/bin/ldapsearch -LLL -x -y ~/.ldappasswd -H ldap://ldap.marsel.is -D 'cn=admin,dc=marsel,dc=is' -b "" -s base
/usr/bin/ldapsearch -LLL -x -y ~/.ldappasswd -H ldap://ldap.marsel.is -D 'cn=admin,dc=marsel,dc=is' -b "" -s base '(objectclass=*)' +
# /usr/bin/ldapsearch -LLL -x -w 12345 -H ldap://ldap.marsel.is -D 'cn=admin,dc=marsel,dc=is' -b "" -s base
# with filter and operational attributes
/usr/bin/ldapsearch -LLL -x -y ~/.ldappasswd -H ldap://ldap.marsel.is -D 'cn=admin,dc=marsel,dc=is' -b "" -s base '(objectclass=*)' +
# '(objectclass=*)' is the broadest filter — matches any entry. Cannot be simplified to '()': an empty filter is invalid LDAP syntax.
# ansible
ansible-playbook -i inventory.yml slapd.yml
# TODO: after finishing book, translate all commands to NVI:
#   - suffix dc=nvi,dc=no
#   - rootdn cn=admin,dc=nvi,dc=no (admin account)
#   - personal account: uid=vi2158,ou=people,dc=nvi,dc=no (or equivalent OU)

# LDAP filter syntax (RFC 4515) - prefix/Polish notation
# operators: & (AND)  | (OR)  ! (NOT)
# operator comes FIRST, operands follow

# single filter
(attribute=value)

# operators
(&(filter1)(filter2))        # AND
(|(filter1)(filter2))        # OR
(!(filter))                  # NOT

# comparison operators
(attr=value)                 # equal
(attr~=value)                # approximate
(attr>=value)                # greater or equal
(attr<=value)                # less or equal
(attr=*)                     # present (attribute exists)
(attr=val*)                  # substring (starts with)
(attr=*val)                  # substring (ends with)
(attr=*val*)                 # substring (contains)

# nested example
(&(|(mail=m*)(mail=n*))(roomNumber>=300))
# expanded:
# (&
#   (|
#     (mail=m*)
#     (mail=n*)
#   )
#   (roomNumber>=300)
# )
