**LDAP v4 Design Notes**

**Identity and Authentication**

Passwords not stored in the directory. Authentication via Kerberos exclusively. The directory is not in the auth path. No intermediate "store hashed passwords" solution : hashes are bulk-extractable and one ACL bug or compromised admin exposes every credential. Kerberos limits blast radius to one principal per compromise.

SASL:DN mapping is a directory lookup, not an `authz-regexp` regex in `slapd.conf`. The directory already knows where the user lives.

`-D` flag eliminated. Identity comes from session context : Kerberos ticket, TLS client cert, or active bind. No manual DN injection on the command line or in tools.

`-x` flag eliminated. Bind method is determined from session context. No opt-in flag for simple bind.

TLS mandatory. No `-z`/`-zz` distinction. The client tries TLS, fails, disconnects. Cleartext connections refused by the server. No flag needed, no opt-in, no silent fallback to cleartext.

`ldapwhoami` kept but no `-D` required : returns identity from session context. `ldapwhois` added as the complementary lookup tool.

**Passwords**

No passwords in the directory. `slappasswd` eliminated. `ldappasswd` silently redirects to the Kerberos password change operation : same interface, Kerberos backend, transparent to the user. `password-hash` directive eliminated : no hash algorithm to configure because no passwords are stored. Server-generated passwords eliminated : password generation is a client-side concern. `ldapmodify` and `ldapadd` cannot set `userPassword` : the attribute does not exist.

**Tooling**

`slapcat`, `slapadd` eliminated. Replaced by `ldapexport` and `ldapimport`. One tool, one output : stored and computed attributes both returned. No split between operational and user attributes. No hidden attributes. Backend implementation is irrelevant to the user.

`changetype` eliminated from LDIF records. Operation is a flag on the command, never embedded in data. Data files contain data only : no executable directives. Prevents injection of unintended operations through data payloads.

`ldapadd`, `ldapdelete`, `ldapmodrdn` etc. are shell wrappers around `ldapmodify --add`, `ldapmodify --delete`, `ldapmodify --rename`. No `argv[0]` detection in the binary.

`modrdn` default is replace : old RDN value removed unless `--keep-old-rdn` is explicitly specified. Keeping stale values requires opt-in.

Compound RDNs eliminated. `entryUUID` is the stable identity. DN is a single-attribute path. No `+` syntax in DNs.

`modrdn` as a concept eliminated for entry moves. Rename is a delete and re-add : atomic, explicit, no ambiguity about old values. No dummy RDN required to move an entry to a new superior. `entryUUID` is the stable identity. DN is a path.

`slapacl` replaced by a tool that returns the effective ACL set as structured data. Verification is the caller's problem. Ansible modules provided for ACL testing and enforcement as policy-as-code.

`slapauth` eliminated. SASL:DN mapping is a directory lookup, not a regex test tool.

`slapdn` eliminated. Schema validation is a library call, not a binary.

`slaptest` eliminated. Config validation is a library call : `slapd --test` or a validate function. Not a separate binary.

`ldap4-validate` : migration tool that takes an existing RFC 4515 command, flags deprecated syntax (`*`, `+`, `-D`, `-x`, `-z`, Polish notation filters, short attribute names), and shows the LDAP v4 equivalent. `--fix` mode rewrites in place like `sed`.

All operational tool warnings silent by default. Tools know their own constraints : logging them on every invocation is noise, not signal.

Backend capability limitations are not exposed to the user. If an operation is valid in the schema it must work regardless of backend.

**Client and Configuration**

`ldap.conf` and `~/.ldaprc` eliminated. Client defaults come from the directory. Server advertises its own base, the client discovers it on connect. Session context pushed to the client on bind : the server tells the client "you authenticated as X, here is your context."

`-b` flag eliminated. Base DN from session context. `-f` flag eliminated. Use stdin redirect instead: `ldapsearch < queries.txt`.

`-h` and `-p` eliminated. `-H` takes a full URL: `[ldap[s]://]host[:port]`.

`-L`/`-LL`/`-LLL` output format flags eliminated. One output format. Result count not in default output : optional flag or count `entryUUID` occurrences.

`*` and `+` specifiers eliminated from attribute lists. Name what you want. Attribute tab-completion from session context on connect : client queries `cn=Subschema` on connect, caches for the session, exposes as tab completion. Glob/regex patterns for attribute selection: `e*` returns all attributes starting with `e`.

Short attribute name aliases eliminated. Full attribute names only : `surname` not `sn`, `commonName` not `cn`.

Blank line as record delimiter eliminated. Explicit record terminator : `--` or equivalent sentinel. No invisible whitespace with semantic meaning.

**Filter Syntax**

RFC 4515 Polish notation replaced with human-readable infix syntax. `ldapsearch "surname = Jensen"` : no parentheses, no special characters required for common operations. Polish notation remains valid input for compatibility. Filter translation tool converts RFC 4515 to infix and back : bidirectional, same function as `EXPLAIN` in SQL.

Parameterized query substitution: `%s0` through `%sN` for multiple positional parameters. Batch queries from stdin with full parameter binding. No string concatenation, no injection risk.

**ACLs**

ACLs stored in the database, not in a flat config file. TUI or structured CLI for authoring and testing. Test cases stored alongside ACL definitions, verifiable without a live server. ACLs ship with opinionated defaults, documented rationale, edge case guide, and a guarded reset path : confirmation required, not a one-liner. Point-and-call acknowledgment before any destructive ACL change.

Ansible modules provided for ACL testing and enforcement as policy-as-code.

**Architecture**

Privilege separation: slapd is protocol frontend, database process is backend with its own ACL authority. slapd serves requests and does not evaluate access decisions. Access decision is the db layer's responsibility.

OLC mirrored to the database, not the authority. Main thread reads only the compiled-in config snapshot. A separate thread handles config sync. Config diffability is a tooling problem, not an architecture problem.

All write operations atomic, auditable, and reversible. Every change logged with `entryUUID`, timestamp, and principal. Rollback to any previous state. No silent side effects.

`entryUUID` is the stable identity across all operations. DN is a path.

Domain join as first-class operation in preseed/kickstart : not a post-boot afterthought. Automount for clients included. Share configuration pushed from the directory. Policy lives in the directory, applied at provision time, enforced on drift : GPO equivalent, declarative, Ansible-backed.

**Compatibility**

Modern LDAPv3 tooling shipped first : sane flags, no `changetype` in data, TLS mandatory, tab-completion : all against an LDAPv3 server. Proves the design, builds the ecosystem. LDAPv4 protocol changes follow.

Simple bind compatibility shim: speaks simple bind on the legacy side, Kerberos on the backend. Free to use, supported commercially. Deprecation date announced at launch.

Patches offered to major LDAP-integrated applications (Confluence, Jira, Jenkins, GitLab, Grafana, Nextcloud, etc.) to replace simple bind with SASL/Kerberos.

**Licensing**

GPL3. One license, no tiers, no enterprise edition carveout.
