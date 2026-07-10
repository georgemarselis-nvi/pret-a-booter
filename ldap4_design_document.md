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

`ldapmodify` takes subcommands : `ldapmodify add`, `ldapmodify delete`, `ldapmodify rename`. One binary, one argument grammar, same pattern as `git add`/`git commit`. The operation is the first word after the binary name, not a flag buried among others.

`ldapadd`, `ldapdelete`, `ldapmodrdn` retained as symlinks to `ldapmodify` for compatibility and muscle memory : `ldapadd` is `ldapmodify add`, `ldapdelete` is `ldapmodify delete`, `ldapmodrdn` is `ldapmodify rename`. No `argv[0]` detection inside the binary itself : the symlinks are transparent aliases, not a parsing branch.

`modrdn` default is replace : old RDN value removed unless `--keep-old-rdn` is explicitly specified. Keeping stale values requires opt-in.

Compound RDNs eliminated. `entryUUID` is the stable identity. DN is a single-attribute path. No `+` syntax in DNs.

`modrdn` as a concept eliminated for entry moves. Rename is a delete and re-add, wrapped in an explicit transaction : delete succeeds only if re-add succeeds, re-add succeeds only if delete succeeds. Partial failure rolls back automatically. No dummy RDN required to move an entry to a new superior. `entryUUID` is the stable identity and survives the operation unchanged. DN is a path.

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

Default DIT structure mandatory, not advisory. LDAP v4 ships with a canonical DIT layout (`ou=users`, `ou=groups`, `ou=services`, etc.) baked into the spec, not left to each installation to invent independently. Every admin, every tool, every piece of documentation can assume the same baseline structure exists. No more `ou=people` vs `ou=users` vs `cn=Users` fragmentation across installations : that flexibility-with-no-default is exactly the failure mode the rest of this design rejects.

AD-compatible alias layer : LDAP v4 supports a configurable alias mapping so the canonical DIT and schema can present themselves under Active Directory naming conventions (`cn=Users` aliasing to `ou=users`, attribute name aliasing for the handful of places AD and RFC schema diverge). Goal is 100% surface compatibility for AD-trained admins and AD-targeting tooling, without forcing the underlying directory to adopt AD's actual design flaws. Lowers the migration barrier for the largest population of directory admins in existence, who have only ever worked against AD.

**Transport Security**

StartTLS deprecated in LDAP v4. RFC 4513 deprecated : the 2006 IETF decision to prefer StartTLS over LDAPS was wrong, practice and security analysis both confirm it. LDAPS only on port 636, mandatory, no exceptions, TLS from byte one. Plaintext port 389 removed. LDAP v5 : TLS mandatory at the protocol level, no plaintext negotiation path exists. StartTLS is a downgrade attack surface : plaintext window before upgrade, client can continue cleartext if upgrade fails.

`ldapi:///` (Unix domain socket) retained exclusively as a break-glass operational recovery path, not a security mechanism : if you have root on the box you already own the directory. TLS required even over the socket, for uniformity with LDAPS (no special code path) and to prevent credential exposure to other local processes. Break-glass authentication requires username, password, and a client certificate stored on a YubiKey with non-exportable private key : box presence, credentials, physical key, and PIN. By the time break-glass is needed something has already gone wrong; identity must be unambiguous and fully auditable. The break-glass client certificate is managed through `libcertstore`'s PKCS#11 module : same mechanism as any other hardware-token-backed cert, no separate cert management path for the break-glass account.

Legacy cleartext proxy: a separate proxy program accepts plaintext on port 389, terminates TLS toward the server, and proxies the connection. Stepping-stone for apps that cannot be patched. In LDAP v5 the proxy is declared end-of-life and removed. No cleartext path exists anywhere in the stack after that.

**Schema**

No binary blobs. The directory is not a fileserver. Binary attribute syntaxes (OctetString for images, audio, certificates as inline data) are not supported. Photo and audio attributes store URLs only : `jpegPhotoURL`, `audioURL`. Clients are responsible for fetching and rendering. Swapping the file does not require touching the directory entry. Binary data does not bloat replication.

`userCertificate` and related X.509 attributes stored inline as binary : temporary exception. Deprecated pending Kerberos 6 and `libcertstore`, the canonical local certificate store. When `certstored` is available, certificate attributes become URLs pointing at `certstored`-served certs, retrieved via the daemon's signed delivery mechanism rather than embedded as binary blobs. Binary inline certs removed in LDAP v5.

`sshPublicKey` (per draft-leverett-ldap-ssh-keys) mandatory on user entries, nullable. Public keys are not secret. Enables centralized `authorized_keys` management via `AuthorizedKeysCommand`. Clients pull directly from the directory. No binary, no URL indirection needed. Empty value permitted : Windows users and service accounts may have no SSH key. This attribute is the distribution mechanism for `libcertstore`'s SSH key rotation: `certctl rotate` rotates the key in the store, the new public key propagates via this attribute to every server's `AuthorizedKeysCommand`, and the client's `ssh-agent` picks up the new identity through `libcertstore`'s PKCS#11 module. No file copied by hand at any point in the chain.

**Provisioning and Migration**

HR provisioning tool takes JSON from the HR system and maps fields to LDAP attributes. Mandatory fields must be present in the JSON or provisioning fails. Nullable fields left empty if absent. Same tool handles updates : re-run on HR data change, only dirty attributes written. No custom query language, no proprietary format.

`ldapexport --json` and `ldapimport --json` for jq interop. Export produces standard JSON, import consumes it. Transformation, filtering, and field mapping done with jq : no custom tooling, no proprietary query language. Canonical LDAP-to-JSON RFC proposal : standardizes how entries, attributes, multi-valued attributes, operational attributes, and DNs map to JSON. One format, all implementations compatible. Prerequisite for `ldapexport --json`, `ldapimport --json`, and browser-native LDAP.

Migration tool exports an LDAPv3 directory to JSON, maps known attributes to the LDAPv4 schema, and produces a per-record diff : old schema left, new schema right, unknown or unmapped attributes flagged for review. Nothing dropped silently. People see exactly what changes before they commit. Gives LDAPv3 operators a clear picture of what migration entails.

**Browser-Native Client**

Official LDAP v4 client ships as a Chrome extension first, before being proposed as a browser standard backed by adoption data. Registers the `ldaps://` URL scheme via manifest `protocol_handlers` : typing `ldaps://hostname/base-dn` in the address bar opens the directory directly, same as `https://` today.

Authenticates via OS-session Kerberos ticket when available; falls back to a server-declared auth form (username/password/OTP) rendered from a JSON schema returned by the server, the same negotiation pattern WebAuthn/FIDO2 already uses for HTTP.

Renders the DIT as a browsable, editable tree : click an attribute to edit it inline, add an unset MAY attribute, drag an entry to a different OU to move it. Renders the schema inheritance hierarchy as an interactive diagram, the live equivalent of the wall poster. Supports LDIF drag-and-drop import and one-click export : no `slapcat`, no `ldapadd`, no command line required for bulk operations.

Server distinguishes browser clients from native LDAP clients via ALPN / content negotiation and returns JSON to browsers, BER to native clients : one server, one port, multiple representations.

Bundled with the LDAP v4 distribution as the primary documented interface. All examples and tutorials in the official documentation use the browser client first; CLI tools are documented as secondary. New admins are onboarded through the browser, not man pages.

**Compatibility**

Modern LDAPv3 tooling shipped first : sane flags, no `changetype` in data, TLS mandatory, tab-completion : all against an LDAPv3 server. Proves the design, builds the ecosystem. LDAPv4 protocol changes follow.

Simple bind compatibility shim: speaks simple bind on the legacy side, Kerberos on the backend. Free to use, supported commercially. Deprecation date announced at launch.

Patches offered to major LDAP-integrated applications (Confluence, Jira, Jenkins, GitLab, Grafana, Nextcloud, etc.) to replace simple bind with SASL/Kerberos.

**Licensing**

GPL3. One license, no tiers, no enterprise edition carveout.

- **ACL engine has no "server itself" identity.** The authz resolution
  search is modeled as anonymous only because slapd's ACL namespace
  contains bind identities (anonymous, users, DNs) but no concept of
  the server reading its own directory for its own auth machinery. This
  forces granting anonymous read on uid just to make the server's own
  resolver work. Backwards. ldap4: identity resolution is an internal
  server capability (read uid under the user subtree), not an entry in
  the ACL namespace. Nothing anonymous is granted; no external identity
  can inherit the resolver's read.

## Historical leftovers from X.500

LDAP inherited vocabulary and structure from X.500/OSI that no longer
describe what the operations do. ldap4 keeps the wire behavior where
compatibility demands it but does not treat the inherited names as
sacred.

Known leftovers:

- **bind / unbind.** X.500 terms for attaching an identity to an
  application association (connection), by analogy to binding to a
  socket. "Bind" does not mean "authenticate" in the abstract; it means
  "associate this identity with this connection." The modern operation
  is unchanged and necessary. Only the name is a leftover. Client verb
  undecided; not a priority.

- **Anonymous pre-auth search.** The authz identity resolution search
  runs as anonymous because no identity exists yet at that point. This
  is a structural leftover, not a feature. ldap4 replaces it with a
  scoped internal resolver identity (read uid under the user subtree
  only), never anonymous, never omnipotent.

- **DN as both name and location.** Inherited assumption that an entry's
  name encodes its position in the tree. Retained, but see the
  narrowest-subtree and no-cross-authority-dereference rules for how
  ldap4 constrains what that location may be used for.

Rule: inherited names are cosmetic and may be modernized, but renaming
is polish, never protocol progress. Semantics come first.


- **Mapping failure does not fail the bind.** In slapd, if authz-regexp
  authenticates a SASL identity but the mapping search finds no DIT
  entry, the bind still succeeds with the raw auth identity
  (uid=x,cn=GSSAPI,cn=auth). Fail-open: an authenticated-but-unmapped
  session exists, and loose ACLs (by users) can grant it access.
  ldap4: mapping failure is bind failure. No entry, no session. Authc
  and directory identity may never diverge.

- **Uppercase realm convention.** K5 uppercases realms (MARSEL.IS) only
  to distinguish them visually from DNS names; no meaning. Kerberos 6:
  realms lowercase, DNS-qualified, canonical. Accepts K5 uppercase
  input case-insensitively, folds to lowercase.
- **Principal case.** Case-preserving, case-insensitive-unique. The user
  picks their display case (names are personal), but George and george
  cannot both exist. Store as-entered for display plus a folded
  lowercase key for uniqueness and lookup. Collision checks and lookups
  use the folded key; display uses the original.

- **Realm defaulting.** slapd's sasl-realm is a soft default: the client
  may omit the realm and get this one, or send a different realm and
  have it accepted. ldap4: the realm is fixed to the server's single
  storage authority. Omitting the realm implies the local realm. Sending
  a DIFFERENT realm is not a defaultable value -- it is a cross-realm
  request, resolved only through explicit inter-realm trust, never
  silently accepted at bind. Local realm is the only value, not a
  mutable default.

- **Identity translation between cert DN and directory DN.** X.509
  subject DNs and directory DNs are separate namespaces that share
  X.500 syntax by accident of common ancestry. slapd bridges them with
  a per-deployment authz-regexp: a hand-written guess, not a defined
  mapping. ldap4: no implicit translation. The certificate names the
  directory identity directly, or the cert carries an explicit,
  standardized identity claim. Any mapping between namespaces is an
  amendment to the standard, declared once, not a regex each admin
  invents.

- **Naming is structurally unspecified.** X.520/RFC 4519 defines cn as a
  human-readable name: no uniqueness, no stability, no machine
  semantics. RFC 4514 defines DN string syntax and X.501 the RDN model,
  but neither mandates which attribute types name which entry kinds.
  The standard specifies grammar, never meaning. Every deployment
  invents its own convention, which is why cert-DN-to-directory-DN
  mapping is a per-site regex rather than a defined function.

  ldap4: naming is mandatory and fixed.
  - Users are named by uid. Always. uid is the identifier: unique,
    stable, machine-readable, never reused.
  - cn is display only. It is never an RDN, never an identifier, never
    parsed, never mapped.
  - Entry kind determines RDN attribute by rule, not by deployer choice.
  - Certificates name the directory identity directly. No scraping cn.

- **ACLs as ordered flat-file directives.** slapd evaluates access rules
  sequentially, first match wins, order determined by position in
  slapd.conf. Correctness depends on invisible file ordering; the book
  repeatedly instructs "put this rule at the top." Moving a rule
  silently changes authorization.

  ldap4: ACLs are entries in the database, managed via `ldapctl acl`.

  - **Full evaluation, not first-match.** Every rule applicable to the
    target entry and attribute is evaluated. There is no early exit, so
    rule order carries no meaning and cannot be a source of silent
    breakage.
  - **Deny wins.** A deny at any depth overrides an allow at any depth.
    Fail-closed. This is only coherent under full evaluation, which is
    why first-match is abandoned.
  - **Recursion is the default.** Rules inherit downward through the
    subtree. Not an option, not a flag.
  - **No implicit ordering.** Insertion order is not semantics. If a
    deployment ever needs explicit precedence, it is a declared
    attribute on the rule, queryable and auditable, never file position.
  - **Decisions are explainable.** Every authorization decision can be
    traced: `ldapctl acl explain <dn> <attr> <identity>` returns every
    rule that matched, which granted, which denied, and why the result
    is what it is. Not a debug mode: a first-class operation, always
    available.
  - **Shadowing is detectable.** Because all matches are evaluated,
    `ldapctl acl lint` can report rules that can never grant anything
    (fully shadowed by a deny) or that overlap ambiguously. Under
    first-match-wins these rules are invisible dead code.

## Client tooling

Single binary, subcommand grammar: `ldapctl`.

Replaces the ldapsearch/ldapadd/ldapmodify/ldapdelete/ldappasswd family.
Consistent with `certctl` (libcertstore). Subcommands are nouns then
verbs: `ldapctl acl explain`, `ldapctl entry get`, `ldapctl schema show`.

## Machine interface

`ldapctl` supports `--json` for both input and output on every
subcommand.

- **Output**: structured JSON, stable schema, suitable for parsing.
  Human-readable text is the default; `--json` is the contract.
- **Input**: declarative. `ldapctl entry set --json` applies desired
  state and reports what changed. Idempotent by construction: applying
  the same document twice is a no-op. This is the property Ansible and
  any other configuration tool requires.
- **LDIF** remains the interchange format for import/export with other
  directory implementations. JSON is the machine interface; LDIF is the
  wire format for portability. Both, not one.
- Exit codes are meaningful and documented. No parsing stderr to find
  out what happened.

- **No binary values.** All attribute values are UTF-8 strings. LDIF
  base64 (`::`) is removed; JSON needs no encoding tag; conversion
  between LDIF and JSON is semantically lossless with no binary
  special-case.
  - `jpegPhotoURL`, `audioURL`: URLs, clients fetch and render.
  - `userCertificateURL`: URL pointing at the issued certificate,
    served by the CA. Replaces inline DER `userCertificate`. The CA is
    the authority for cert material; the directory holds a reference,
    not a copy.


