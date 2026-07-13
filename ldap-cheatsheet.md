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
ldapsearch -x -b cn=subschema -s base matchingRules  | grep -oE "NAME '[^']+'|[0-9.]+"


## The by phrase: by <who> [<access>] [<control>]

access to <what>
        by <who> <access> <control>

### <who> — which requester

*                  everyone
anonymous          unauthenticated clients (mostly for userPassword auth)
users              any authenticated client
self               the entry accessing its own record
dn.<style>="..."   a specific DN (exact/base/one/subtree/children/regex)
dnattr=<attr>      DN(s) named in that attribute of the target entry
group="..."        members of a group entry
peername="..."     client network address/name
sockname="..."     server socket name
domain="..."       client domain (see next section for traps)
sockurl="..."      listener URL
set="..."          set-expression match

### <access> — level granted (each level implies all below it)

manage    m   full control incl. schema-violating changes
write     w   modify (= a + z + i)
add       a   add a value/entry
delete    z   delete a value/entry
increment i   increment (numeric)
read      r   read values
search    s   apply in a search filter
compare   c   compare a value
auth      x   use for authentication (bind)
disclose  d   allowed in error messages (vs. hidden)
none      0   no access at all

# level implication: write also grants read, search, compare, auth,
# disclose. Grant a named level, or use privilege flags for exact sets.

### <priv> — exact privilege flags (instead of a level)

=<flags>   set access to exactly these flags (resets prior)
+<flags>   add these flags
-<flags>   remove these flags
flags: m w a z i r s c x d, or 0 for none

# examples
by * =rscd          exactly read+search+compare+disclose, nothing else
by users +r         add read to whatever earlier clauses granted
by self -w          remove write

### <control> — flow after a match

stop       (default) matching stops; decision is final
continue   keep evaluating later by clauses in THIS rule
           (privileges accumulate incrementally)
break      stop this rule, jump to the next access-to rule

# implicit terminator on every who-list:
#   by * none stop

### worked example (privilege accumulation with break)

access to *
        by dn.exact="cn=admin,dc=marsel,dc=is" write stop
        by * break
# admin gets write and evaluation stops; everyone else falls
# through to the next rule instead of hitting the implicit deny.


## ACL traps

### Level implication is silent
Granting a level grants every lower level too. `write` also gives read,
search, compare, auth, disclose. For modify-without-read you MUST use
privilege flags, not a level.

  by <who> write        -> also readable by <who>
  by <who> =wx          -> write + auth only, no read

### disclose leaks existence
Without `d`, a denied attribute/entry is invisible (client cannot tell
it exists). Granting `d` reveals existence via error messages. Default
hides; add `d` deliberately.

### self is the accessor, not the target
`self` matches when accessor DN == target DN. With proxy/group traversal
it is still the accessor, not what you may assume. self.level{n} shifts
which ancestor is compared: off-by-one prone.

  self.level{1}   an ancestor of the accessor
  self.level{-1}  an ancestor of the target

### continue accumulates privileges
With `continue`, later by-clauses in the same rule keep modifying the
grant. Reading one clause in isolation does not give effective access;
you must sum the chain.

### = resets, + / - adjust
`=flags` wipes accumulated privileges and sets exactly those. `+`/`-`
add/remove from what earlier clauses granted. Mixing `=` and `+/-`
across `continue` makes effective access non-obvious.

  by * =r     exactly read, discards prior
  by * +r     read added to prior
  by * -w     write removed from prior

### domain= is forgeable reverse-DNS
by domain= / peername= match network identity via reverse DNS or IP,
spoofable, and not authentication. Never a standalone grant.

### first-match-wins hides later rules
slapd stops at the first matching <what>. A broad early rule shadows
narrower later ones. Rule ORDER is semantic; moving a rule changes
authorization silently.

### implicit terminator
Every who-list ends with an implicit `by * none stop`. If your rule did
not grant it, it is denied here, even if a later rule would have granted
it (unless you used break).

- **rootdn bypasses all access control, unconditionally.** cn=admin
  (rootdn) ignores every ACL; by * none does not apply. One identity
  with total, unrestrictable, unauditable power, a single point of full
  compromise, retained because early slapd needed a break-glass account
  that could not lock itself out.

- **rootdn naming drift (cn=Manager vs cn=admin).** The superuser is
  whatever DN rootdn names; it is not a fixed identity. OpenLDAP docs
  use cn=Manager, Debian uses cn=admin, others differ. Same role, no
  canonical spelling, so every deployment's break-glass DN is different
  and cross-references (docs, playbooks, runbooks) silently mismatch.

## Access levels as privilege sets

Each level is shorthand for a cumulative flag set. Higher levels include
all lower flags (the silent implication).

Keyword  | Flags   | Adds
---------|---------|------------------
none     | 0       | nothing
disclose | d       | disclose
auth     | xd      | + authenticate
compare  | cxd     | + compare
search   | scxd    | + search
read     | rscxd   | + read
write    | wrscxd  | + write

# so `write` silently grants w r s c x d.
# for an exact set instead of a level, use flags: by * =rd

## self / realself prefixes (fused level keywords)

- **self/realself prefixes fused onto levels.** selfwrite, selfread,
  realselfcompare... = the prefix (value must be the accessor's own DN)
  welded to the level into one token, producing 7 levels x 2 prefixes
  of fused keywords.

The capability is good:
- selfwrite on uniqueMember lets a user add/remove ONLY their own DN
  (self-service group join/leave, no admin touch to others).
  Example: access to attrs=uniqueMember by users selfwrite
- realself = same, but rejects PROXIED DNs (a proxy-authz identity
  binding as you cannot use it). Tighter.

The spelling is not: prefix (self-scope) and level (capability) should
be orthogonal, not welded into one keyword.

ldap4: self-scope is an orthogonal condition on the rule, not a
keyword prefix.
  grant write to uniqueMember where value = self
  grant write to uniqueMember where value = self and not proxied  # realself
Condition and capability stay separate; no NxM keyword explosion.

- **23-form <who> field.** slapd's who field has ~23 combinable forms
mixing three unrelated axes: authenticated identity (self, dn, users,
anonymous), network origin (peername, sockname, domain, sockurl), and
membership/set (group, dnattr, set, aci). One grammar, all
interacting with accumulation and ordering.

ldap4: the axes are separate concerns, not one field.
- identity: who the authenticated principal is (or a group it belongs
  to). The only thing that grants access.
- network origin: a coarse pre-filter, optional, never a grant on its
  own (see domain= trap).
- membership/set: expressed as a predicate/query, not a who-keyword.
No combinatorial who-soup.

- **23-form <who> field.** slapd's who field has ~23 combinable forms
  mixing three unrelated axes: authenticated identity (self, dn, users,
  anonymous), network origin (peername, sockname, domain, sockurl), and
  membership/set (group, dnattr, set, aci). One grammar, all
  interacting with accumulation and ordering.


- **Proxy authorization (authz).** One identity authenticates (real DN),
  operations run as another (authz DN), gated by authzTo/authzFrom.
  Lets a service act on behalf of users without per-user binds. Risk: a
  compromised proxy acts as anyone it may proxy. slapd adds real*
  who-forms (realdn, realself, realusers, realanonymous) to match the
  authentication DN, not the proxied one.

## group specifier (by group=...)

Grant access to members of a group. slapd needs the group's objectClass
and membership attribute spelled out unless you use the defaults.

# default: groupOfNames + member
by group="cn=Admins,ou=Groups,dc=marsel,dc=is" write

# explicit objectClass + membership attribute
by group/groupOfUniqueNames/uniqueMember="cn=LDAP Admins,ou=Groups,dc=marsel,dc=is" write

# form
by group[/<objectClass>[/<attr>]]="<groupDN>" <access>

# groupOfNames        -> member       (default)
# groupOfUniqueNames  -> uniqueMember (must specify both)

## by-phrase specifiers: styles + examples

Each specifier takes a style suffix (.<style>) selecting how the value
is matched. Network/connection specifiers are a coarse filter only,
never a standalone grant (spoofable / not authentication).

### peername  (client connection address)
peername.ip="IP[%mask][:port]"    IPv4, optional mask + source port
peername.ipv6="[::1]"             IPv6 literal
peername.path="/var/run/ldapi"    ldapi socket path
peername.exact="..."              exact match on the peer name
peername.regex="..."              regex against the peer name
# raw peer name forms: IP=10.0.0.5:1234  or  PATH=/var/run/ldapi

by peername.ip="10.0.0.5" read
by peername.ip="10.40.0.0%255.255.255.0" read      # /24 subnet
by peername.path="/var/run/ldapi" write
by peername.regex="^IP=(10\.10\.10\.10|1\.1\.1\.1):[0-9]+$" read

# peername.regex matches the RAW string "IP=<addr>:<port>"
# must include IP= prefix and :port, or it never matches
by peername.regex="^IP=10\.40\.12[0-9]:[0-9]+$" read

### sockname  (server listener socket name)
sockname.exact="/var/run/ldapi"
sockname.regex="..."

by sockname.exact="/var/run/ldapi" write

### domain    (client reverse-DNS hostname; forgeable)
domain.exact="host.marsel.is"     exact hostname
domain.subtree="marsel.is"        host and any subdomain
domain.regex="..."                regex against the hostname

by domain.exact="host.marsel.is" read
by domain.subtree="marsel.is" read

### sockurl   (listener URL the client connected to)
sockurl.exact="ldap://ldap.marsel.is"
sockurl.regex="..."

by sockurl.exact="ldap://ldap.marsel.is" write

### ssf family (numeric, no styles; comparison is >=)
ssf=<n>              overall connection SSF
transport_ssf=<n>    transport-layer SSF
tls_ssf=<n>          TLS-layer SSF
sasl_ssf=<n>         SASL-layer SSF

by ssf=256 write
by tls_ssf=256 read
by sasl_ssf=256 read
by transport_ssf=256 read
# SSF values: 0 cleartext, 56/112 obsolete, 128 AES-128, 256 AES-256/TLS1.3

### dn (who)  — same styles as access-to dn
dn.exact  dn.base  dn.one  dn.subtree  dn.children  dn.regex

by dn.exact="uid=barbara,ou=Users,dc=marsel,dc=is" write
by dn.children="ou=System,dc=marsel,dc=is" read
by dn.regex="uid=[^,]+,ou=Users,dc=marsel,dc=is" read

### group (who)
group="cn=...,ou=Groups,..."                       default OC/attr
group/<objectClass>/<attr>="cn=..."                explicit OC + attr

by group="cn=Admins,ou=Groups,dc=marsel,dc=is" write
by group/groupOfUniqueNames/uniqueMember="cn=LDAP Admins,ou=Groups,dc=marsel,dc=is" write

### dnattr (who: requester DN appears in target's attribute)
by dnattr=uniqueMember write        # members can modify their own group

### combined (AND: all specifiers in one clause must match)
by peername.ip="10.40.0.0%255.255.255.0" ssf=256 write

# every rule ends with an implicit: by * none

Notes:
- .exact = literal compare; .regex = POSIX ERE.
- peername.ip mask uses % not / :  10.40.0.0%255.255.255.0
- domain relies on reverse DNS; never use as a grant.

- **domain= matches the reverse-DNS canonical (A-record) name, not the
  CNAME.** slapd reverse-resolves the client IP; PTR returns the
  A-record host (mercury.example.com), never the CNAME alias
  (ldap.example.com). An ACL written against the alias silently never
  matches. Yet another reason network-name specifiers are unfit as
  grants. ldap4: no domain=; identity comes from authentication, not
  DNS names.

- **Client-cert requirement is global, not per-ACL.** slapd cannot
  require a client cert for a specific target via ACL; TLSVerifyClient
  demand is a global slapd.conf directive. So "domain= is only safe with
  a cert" cannot be enforced where domain= is used, only server-wide.
  ldap4: authentication strength is expressible ~~per-target in the same
  rule system, not split between global config and ACLs.~~global

- **set= is set-algebra as an ACL escape hatch.** When group/dnattr
  cannot express a relationship, slapd offers set= : a full
  set-theoretic language (intersection &, union |, DN/attribute
  traversal) written inline per rule. Powerful, opaque, overkill for
  the 99% case ("is X a member of Y"). ldap4: relationships
  (membership, ownership, delegation) are first-class, server-resolved
  predicates, not hand-written set math. No set= mini-language.

## limits: per-identity size/time limits (database section)

Overrides global sizelimit/timelimit per consumer. One line per
consumer class, in the database stanza.

    limits <who> <limit-phrase>...

who:
    users                       all authenticated users
    anonymous                   (dead on our server: bind_anon off)
    dn.exact="cn=svc,..."       one identity
    dn.subtree="ou=services,..."
    dn.regex="^uid=.*,ou=x$"    POSIX ERE
    group="cn=admins,ou=groups,..."   member of group

limit-phrases:
    size.soft=N     returned if client requests nothing
    size.hard=N     ceiling on entries returned
    size.unchecked=N  ceiling on candidates EXAMINED; exceeding
                      refuses the search (adminLimitExceeded),
                      pre-execution cost bound
    time.soft=N     seconds, same semantics
    time.hard=N
    unlimited       valid value for any phrase (rootdn already
                    exempt from all limits)

Example, FEIDE bulk consumer:

    limits dn.exact="cn=feide-svc,ou=services,dc=marsel,dc=is"
        size.soft=500 size.hard=unlimited size.unchecked=unlimited
        time.hard=120

Notes:
- evaluated first match wins, order matters (like ACLs)
- timer starts at execution, not arrival: queue wait not counted
- global sizelimit/timelimit still apply to anyone not matched
