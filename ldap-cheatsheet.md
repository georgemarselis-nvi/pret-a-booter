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

## ACL DN scope keywords

| Scope         | Base? | Children? | Meaning                          | Synonyms                   |
|---------------|-------|-----------|----------------------------------|----------------------------|
| `dn.base`     | yes   | no        | the named DN only                | `dn.exact`, `dn.baselevel` |
|`dn.one`       | no    | 1 level   | immediate children only          | `dn.onelevel`              |
| `dn.subtree`  | yes   | all       | the DN plus everything below     | `dn.sub`                   |
| `dn.children` | no    | all       | everything below, not the DN     | none                       |
| `dn.regex`    | n/a   | n/a       | DN matched by regular expression | none                       |

- `dn.subtree` = `dn.base` + `dn.children`
- `dn.one` covers only direct children, not deeper descendants
- `dn.regex="uid=[^,]+,ou=Users,dc=example,dc=com"`

## dn.regex scope

dn.regex is not ACL-only. slapd reuses the same regex DN-matching engine
across config directives:

- ACL selectors: `access to dn.regex=...`, `by dn.regex=...`
- `authz-regexp` (SASL identity to DN mapping)
- `limits dn.regex=...`
- other DN-matching selectors


## Value-level ACLs (val=)

## val= (value-level ACL)

Restrict access by attribute VALUE, not just attribute name.

# exact value
access to attrs=givenName val="Matt"
        by * none

# case-insensitive exact (depends on attribute's matching rule)
access to attrs=givenName val.exact="Matt"
        by * none

# regex value match
access to attrs=mail val.regex="^.*@example[.]com$"
        by * read

# DN-valued attribute, match by subtree
access to attrs=member val.subtree="ou=People,dc=example,dc=com"
        by * read

val styles: regex, subtree, base, one, exact, children
(same styles as the dn specifier)



## Pseudo-attributes: entry and children

Not real attributes. Control the record and the subtree, not values.

# permission to the entry record itself (see/create/delete the object)
access to attrs=entry
        by self read
        by * none

# permission over children (create/delete entries beneath this DN)
access to dn.base="ou=People,dc=example,dc=com" attrs=children
        by dn.exact="cn=admin,dc=example,dc=com" write
        by * none

# adding uid=matt,ou=People requires BOTH:
#   write on children of ou=People   (permission to add under it)
#   write on entry of the new record (permission to create the object)

- **children means two things.** attrs=children is a pseudo-target
  (permission over child entries). val.children is a value-match style
  (attribute value is a DN below a base). Unrelated, same word. ldap4:
  rename so the two never share a token.

val.children="ou=People,..." = match entries whose attribute value is a DN strictly below that base.
attrs=children = permission over the child entries of the target.

## children: two unrelated meanings

`attrs=children` and `val.children` share a word but cannot combine.

# attrs=children : pseudo-target, permission over child ENTRIES
# takes no val (no attribute, no value to filter)
access to dn.base="ou=People,dc=example,dc=com" attrs=children
        by dn.exact="cn=admin,dc=example,dc=com" write
        by * none

# val.children : value-match style for a DN-valued ATTRIBUTE
# value must be a DN strictly below the base
access to attrs=member val.children="ou=Groups,dc=example,dc=com"
        by * read

# INVALID: attrs=children takes no val
# access to attrs=children val.children="..."   <- does not work


## Alternate matching rules (val/)

val compares using the attribute's default equality matching rule.
Override per-ACL with val/<rule>, naming the matching rule or its OID.
The rule must be loaded in the schema and compatible with the
attribute's syntax.

# override to case-sensitive
access to attrs=givenName val/caseExactMatch="Matt"
        by * none

# by OID
access to attrs=givenName val/2.5.13.5="Matt"
        by * none

### Standard matching rules (RFC 4517)

Name                               OID           Use
---------------------------------  ------------  --------------------------
objectIdentifierMatch               2.5.13.0      OID equality
distinguishedNameMatch              2.5.13.1      DN equality
caseIgnoreMatch                     2.5.13.2      string, case-insensitive
caseIgnoreOrderingMatch             2.5.13.3      string ordering, ci
caseIgnoreSubstringsMatch           2.5.13.4      substring, ci
caseExactMatch                      2.5.13.5      string, case-sensitive
caseExactOrderingMatch              2.5.13.6      string ordering, cs
caseExactSubstringsMatch            2.5.13.7      substring, cs
numericStringMatch                  2.5.13.8      numeric string
numericStringOrderingMatch          2.5.13.9      numeric ordering
numericStringSubstringsMatch        2.5.13.10     numeric substring
caseIgnoreListMatch                 2.5.13.11     list, ci
integerMatch                        2.5.13.14     integer equality
integerOrderingMatch                2.5.13.15     integer ordering
bitStringMatch                      2.5.13.16     bit string
octetStringMatch                    2.5.13.17     binary exact
octetStringOrderingMatch            2.5.13.18     binary ordering
telephoneNumberMatch                2.5.13.20     phone (ignores spaces/-)
telephoneNumberSubstringsMatch      2.5.13.21     phone substring
generalizedTimeMatch                2.5.13.27     timestamp equality
generalizedTimeOrderingMatch        2.5.13.28     timestamp ordering
integerFirstComponentMatch          2.5.13.29     integer first component
objectIdentifierFirstComponentMatch 2.5.13.30     OID first component
directoryStringFirstComponentMatch  2.5.13.31     string first component

### List what your server actually loaded

ldapsearch -x -b cn=subschema -s base matchingRules

# or just the names/OIDs
ldapsearch -x -b cn=subschema -s base matchingRules \















