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
# (objectclass=*) — the universal filter
(objectclass=*) matches every entry in the DIT.
Every entry must have at least one objectClass, so this filter always matches.
It is the broadest possible filter — cannot be simplified further.
(objectclass=) is invalid syntax — empty value is not the same as present.
# common use: dump everything under a base DN
/usr/bin/ldapsearch -LLL -x -y ~/.ldappasswd -H ldap://ldap.marsel.is -D "cn=admin,dc=marsel,dc=is" -b "dc=marsel,dc=is" -s sub "(objectclass=*)"
# slapcat — dump database to LDIF on stdout; warnings go to stderr
# output includes operational attributes (entryUUID, entryCSN, creatorsName, etc.)
# intended for slapadd, not ldapadd (operational attrs must be stripped first)
/usr/sbin/slapcat 2>/dev/null
/usr/sbin/slapcat -l /tmp/backup.ldif
/usr/sbin/slapcat -a '(uid=barbara)'
/usr/sbin/slapcat -n 2                                   # explicit db number (2 = first mdb, 0 = config)
# slapacl — test ACL evaluation without a live connection
# -D: DN of the requester (who is asking)
# -b: DN of the target entry (what is being accessed)
# attr/access: attribute and access level to test (read, write, auth, compare, search)
/usr/sbin/slapacl -v -D "cn=admin,dc=marsel,dc=is" -b "uid=barbara,ou=users,dc=marsel,dc=is" "userPassword/auth"
/usr/sbin/slapacl -v -D "uid=gmarselis,ou=users,dc=marsel,dc=is" -b "uid=barbara,ou=users,dc=marsel,dc=is" "userPassword/write"
/usr/sbin/slapacl -v -D "uid=gmarselis,ou=users,dc=marsel,dc=is" -b "uid=gmarselis,ou=users,dc=marsel,dc=is" "userPassword/write"
# slapauth — test SASL identity to DN mapping (authz-regexp)
# -U: SASL username (authcID)
# -X: expected authzDN to validate against
# -M: SASL mechanism (GSSAPI, PLAIN, SCRAM-SHA-256, etc.)
# -R: realm
/usr/sbin/slapauth -f /etc/ldap/slapd.conf -U gmarselis -X dn:uid=gmarselis,ou=users,dc=marsel,dc=is -M GSSAPI
/usr/sbin/slapauth -f /etc/ldap/slapd.conf -U barbara -M PLAIN
/usr/sbin/slapauth -v -f /etc/ldap/slapd.conf -U gmarselis -M GSSAPI
# common ldap client flags (ldapsearch, ldapadd, ldapmodify, ldapdelete, ldappasswd)
# flag  | meaning
# ------+------------------------------------------------------------------
# -D    | bind DN — full DN of the user authenticating (simple bind only)
#       | LDAP v4: eliminated, identity from session context
# -W    | prompt interactively for password
# -w    | password inline (visible in ps aux, avoid in production)
# -y    | read password from file (entire file contents, no trailing newline)
#       | create with: echo -n "secret" > ~/.ldappasswd && chmod 600 ~/.ldappasswd
# -x    | use simple bind (overrides default SASL attempt)
#       | LDAP v4: eliminated, bind method from session context
# -H    | LDAP URL: -H ldap://host:port or -H ldaps://host
# -h    | hostname only (deprecated, backward compat only, use -H)
# -p    | port (deprecated, use -H with port in URL)
# -z    | StartTLS — try TLS, continue cleartext if negotiation fails (stupid)
# -zz   | StartTLS mandatory — disconnect if TLS negotiation fails
#       | LDAP v4: TLS mandatory by default, no flag needed
# -b    | base DN for search scope
#       | LDAP v4: eliminated, server provides context on connect
# -f    | read operations from file
#       | LDAP v4: eliminated, use stdin redirect instead: ldapsearch < queries.txt
# -v    | verbose output
# -L    | output in LDIF format (-LL omits comments, -LLL minimal)
# -s    | search scope: base, one, sub, children
# -a    | alias dereferencing: never, always, search, find
# with ~/.ldaprc in place (URI, BASE, BINDDN set), minimum working search:
ldapsearch -x -y ~/.ldappasswd "(uid=barbara)"
# parametrized queries with -f (current implementation: one parameter only, %s)
# userIDs.txt contains one value per line; ldapsearch substitutes each into %s
# example userIDs.txt:
#   matt
#   barbara
/usr/bin/ldapsearch -LLL -x -y ~/.ldappasswd -H ldap://ldap.marsel.is -D "cn=admin,dc=marsel,dc=is" -b "ou=users,dc=marsel,dc=is" -f userIDs.txt "(uid=%s)" sn
# limitation: only one substitution parameter (%s) per query in current ldapsearch
# LDAP v4: expand to %s0..%sN for multi-column input, no injection risk
# ldapmodify — add, modify, delete attributes and entries
# WARNING: changetype is an instruction embedded in the LDIF data, not a flag
# changetype: add        — add a new entry
# changetype: modify     — modify an existing entry
# changetype: delete     — delete an entry
# changetype: modrdn     — rename the RDN of an entry
# add a new entry from LDIF file
/usr/bin/ldapmodify -x -y ~/.ldappasswd -H ldap://ldap.marsel.is -D "cn=admin,dc=marsel,dc=is" -f new-entry.ldif
# add a single attribute to an existing entry
# new-attr.ldif:
#   dn: uid=barbara,ou=users,dc=marsel,dc=is
#   changetype: modify
#   add: givenName
#   givenName: Barbara
/usr/bin/ldapmodify -x -y ~/.ldappasswd -H ldap://ldap.marsel.is -D "cn=admin,dc=marsel,dc=is" -f new-attr.ldif
# add multiple attributes in one operation (dash separates operations on same entry)
# TODO: test grouped multi-attr add on slapd 2.6.x — book says it works,
#       2.6.2 reportedly rejects it; use dash-separated blocks if grouping fails
# grouped (may fail on 2.6.x):
#   dn: uid=barbara,ou=users,dc=marsel,dc=is
#   changetype: modify
#   add: description title
#   description: Senior researcher
#   title: Dr
# dash-separated (works on 2.6.x):
#   dn: uid=barbara,ou=users,dc=marsel,dc=is
#   changetype: modify
#   add: description
#   description: Senior researcher
#   -
#   add: title
#   title: Dr
# delete ALL values of an attribute
# del-all.ldif:
#   dn: uid=barbara,ou=users,dc=marsel,dc=is
#   changetype: modify
#   delete: title
# WARNING: omitting the value deletes ALL values of that attribute silently
/usr/bin/ldapmodify -x -y ~/.ldappasswd -H ldap://ldap.marsel.is -D "cn=admin,dc=marsel,dc=is" -f del-all.ldif
# delete ONE specific attribute value
# del-one.ldif:
#   dn: uid=barbara,ou=users,dc=marsel,dc=is
#   changetype: modify
#   delete: title
#   title: Senior Researcher
/usr/bin/ldapmodify -x -y ~/.ldappasswd -H ldap://ldap.marsel.is -D "cn=admin,dc=marsel,dc=is" -f del-one.ldif
# rename RDN (modrdn) — deleteoldrdn: 0 keeps old value, 1 removes it
# rename.ldif:
#   dn: uid=barbara,ou=users,dc=marsel,dc=is
#   changetype: modrdn
#   newrdn: uid=bjensen
#   deleteoldrdn: 0
/usr/bin/ldapmodify -x -y ~/.ldappasswd -H ldap://ldap.marsel.is -D "cn=admin,dc=marsel,dc=is" -f rename.ldif
# restore original RDN
# restore.ldif:
#   dn: uid=bjensen,ou=users,dc=marsel,dc=is
#   changetype: modrdn
#   newrdn: uid=barbara
#   deleteoldrdn: 1
/usr/bin/ldapmodify -x -y ~/.ldappasswd -H ldap://ldap.marsel.is -D "cn=admin,dc=marsel,dc=is" -f restore.ldif
# password cracking (lab/educational use only)
# extract hash from directory
/usr/bin/ldapsearch -LLL -x -y ~/.ldappasswd -H ldap://ldap.marsel.is -D "cn=admin,dc=marsel,dc=is" -b "dc=marsel,dc=is" "(uid=gmarselis)" userPassword
# rootpw hash from slapd.conf: {SSHA}mlNdcAZ3XlPsIWTQoMZjbARljPjWm9H6
# SSHA = SHA-1 + salt, base64-encoded. decode to extract hash and salt:
# echo -n '{SSHA}mlNdcAZ3XlPsIWTQoMZjbARljPjWm9H6' | base64 -d | xxd
# crack with john (format=LDAP-SSHA or use --format=raw-sha1)
/usr/sbin/john --format=LDAP-SSHA /tmp/hashes.txt
# crack with hashcat (-m 111 = SSHA)
/usr/bin/hashcat -m 111 '{SSHA}mlNdcAZ3XlPsIWTQoMZjbARljPjWm9H6' /usr/share/wordlists/rockyou.txt
# TODO: crack {SSHA}mlNdcAZ3XlPsIWTQoMZjbARljPjWm9H6 over the weekend (password is 12345, verify the toolchain works)

# TLS client verification (Chapter 4)
# verify the cert chain locally
openssl verify -CAfile /etc/letsencrypt/live/ldap.marsel.is/fullchain.pem /etc/letsencrypt/live/ldap.marsel.is/cert.pem
# check what cert is being served on 636 and who issued it
openssl s_client -connect ldap.marsel.is:636 -showcerts 2>/dev/null | openssl x509 -noout -issuer -subject
# verify server cert against system trust store
openssl s_client -connect ldap.marsel.is:636 2>/dev/null | grep "Verify return code"
# test ldaps with simple bind (-x); requires TLS_CACERT in ldap.conf pointing at system store
# TLS_CACERT /etc/ssl/certs/ca-certificates.crt
ldapsearch -x -y ~/.ldappasswd -H ldaps://ldap.marsel.is -b dc=marsel,dc=is "(objectclass=*)"
# TODO: create SASL user (uid= entry with userPassword: {SASL}username) after reading SASL section
# TODO: configure SASL mechanism restriction to SCRAM-SHA-256/512 only in slapd.conf
