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

- **ACLs as a blank slate.** slapd ships with no meaningful access
  control; the admin writes every rule, including the ones with only
  one correct answer (userPassword must be auth-only; cn=config is
  admin-only; anonymous gets nothing). Every deployment reinvents them
  and some get them wrong. This is a defect in the server, not a task
  for the operator.

  ldap4: structural security defaults are mandatory and shipped. They
  are not templates and cannot be disabled, only extended. Site
  authorization policy sits on top as explicit, explainable rules.
  The admin declares business policy; the admin never has to hand-write
  the rules that protect the directory from itself.

- **ACL evaluation is precomputed, not re-derived per request.** slapd
  walks its rule list on every operation. ldap4 evaluates the full rule
  set (deny-wins, recursive) once, at ACL write time, producing an
  effective permission set per (identity, entry, attribute) scope. The
  request path is a bitmask AND, not a rule walk.

- ACL writes invalidate and recompute the affected scope.
- `ldapctl acl explain` reports the derivation that produced the
  materialized result, so precomputation does not cost auditability.
- Cost moves from the hot path (every read) to the cold path (rare
  policy change), which is where it belongs.

- **Two ACL scopes (global and per-database).** slapd allows access
  directives both outside and inside a database section; they combine
  by file position across two namespaces, with no way to inspect the
  composite. ldap4: ACLs are entries in the DIT and inherit downward
  from the authority's suffix. One scope, one namespace, no global/local
  distinction.

- **DIT structure is unenforced.** X.500 defines DIT structure rules and
  DIT content rules governing which entry kinds may parent which
  others. OpenLDAP does not implement them: any entry may be placed
  under any entry. Combined with unrestricted RDN choice, the tree has
  no enforced shape.

  ldap4: entry kind determines its RDN attribute and its permitted
  parent. Specifically:

  - **Core structure rules are mandatory and not editable.** Users,
    services, groups, and system entries have fixed placement. New entry
    kinds declare their own rules as data, validated against the core;
    a declared rule may narrow but never widen the core.
  - **Kind is immutable.** objectClass determining entry kind cannot be
    modified after creation. Changing kind requires delete and recreate,
    which revalidates placement.
  - **Every write path validates.** add, modrdn, moddn, and import all
    revalidate placement. A legal entry cannot be moved into an illegal
    position, and imported data is never trusted.
  - **User and service subtrees are flat.** No nested OUs beneath them.
    uid=george resolves to exactly one DN, computed, never searched.
    Depth would reintroduce the search this design exists to eliminate.

  A tree with no enforced shape cannot have computable identity
  locations, which is the property everything else depends on.

- **Synonym scope keywords.** slapd accepts dn.sub as a synonym for
  dn.subtree, and abbreviated forms elsewhere. Multiple spellings for
  one meaning, no canonical form.

  ldap4: long form only in stored rules. dn.subtree, never dn.sub.
  ldapctl accepts synonyms on input but rewrites them to canonical long
  form on write (or emits a deprecation warning). Stored config has
  exactly one spelling per concept.

ldap4: no dn.regex anywhere. The objection is correctness, not speed: a
regex over DN strings is a per-deployment guess that breaks when RDN
order or structure changes. DN shape is enforced structure, not a
pattern to match. Where slapd used dn.regex:
- authz mapping: replaced by direct naming (cert/identity names the DN)
- ACLs and limits: match on attributes with a filter, not on DN shape

- **@ notation tab-completion.** ldapctl completes attrs=@<TAB> against
  the loaded schema: lists objectClasses, and on a second tab expands
  the inherited attribute set so the admin sees exactly what @class
  covers before committing. Silent inheritance becomes visible at the
  point of writing the rule.

- **@ inheritance is silent and greedy.** slapd's attrs=@class includes
  every inherited attribute, invisibly. ldap4:
  - Expansion is shown at write time. ldapctl resolves @class to its
    concrete attribute set and displays/logs it; the rule stores @class
    but the resolved set is never hidden.
  - No silent transitive inclusion.

- **@ vs @= notation.**
  - @class  : all attributes of the class, including inherited
             (slapd-compatible, unchanged).
  - @=class : only the attributes the class itself declares, no
             inherited attributes ("this class exactly").

  Both expand visibly at write time: ldapctl resolves to a concrete
  attribute set and shows it before commit. Inheritance is never hidden.

- **val= specifier (value-level ACL).** slapd restricts access by
  attribute value via `attrs=X val="Y"`, with its own regex/subtree/
  base/one/exact/children styles duplicating the dn scope grammar. The
  capability is legitimate; the syntax is another scattered string
  mini-language with duplicated scope keywords.
  ldap4: value-level ACL is a structured predicate (attr, op, value)
  set via ldapctl, same engine as attribute ACLs. No separate val
  grammar, no duplicated scope styles.

- **Prefix (Polish) filter notation.** LDAP filters (RFC 4515) are
  prefix: operator first, self-delimiting groups, e.g.
  (|(|(givenName=Matt)(givenName=Barbara))(sn=Kant)). Machine-simple
  (no precedence rules), human-hostile once nested.

  ldap4: ldapctl accepts infix filter input with normal operators and
  precedence (givenName=Matt OR givenName=Barbara OR sn=Kant) and
  canonicalizes to the wire form. Prefix remains accepted for
  compatibility. Stored/displayed form is the readable infix; the
  prefix wire encoding is an implementation detail, not what the admin
  reads or writes.

## Access privileges: no single-letter flags, no implicit levels

slapd overloads two incompatible systems in one field:
- levels (none, auth, read, write, manage) where each silently implies
  all lower levels: `write` also grants read+search+compare+auth+disclose
- single-letter privilege flags (m w a z i r s c x d) with =/+/- signs
  that add, remove, or reset bits

The result: `write` and `-w` look related but are a level-grant and a
flag-subtraction, cryptic, and effective access requires simulating
the evaluator.

ldap4:

- **Whole words only.** read, write, add, delete, search, compare,
  authenticate, disclose, manage. No m/w/a/z/i/r/s/c/x/d.
- **No implicit level pyramid.** Granting write grants write, not a
  hidden bundle. Each capability is named explicitly. If an identity
  needs read and write, the rule says read and write.
- **Explicit verbs for change.** grant / revoke, not +/-/=. A rule
  states the resulting capability set directly; there is no
  accumulate-then-subtract arithmetic across clauses.

  # instead of:  by uid=x +w   /   by uid=x -w   /   by uid=x =rscd
  grant   read write   to uid=x
  revoke  write        from uid=x
  set     read compare to uid=x    # exact set, replaces prior

- **Effective set is computed and shown, never hand-simulated.**
  ldapctl acl explain <dn> <attr> <identity> prints the resolved
  capability set in whole words. No mental evaluation of level
  implication or flag arithmetic.

- **rootdn bypasses all access control, unconditionally.** cn=admin
  (rootdn) ignores every ACL; by * none does not apply. One identity
  with total, unrestrictable, unauditable power, a single point of full
  compromise, retained because early slapd needed a break-glass account
  that could not lock itself out.

  ldap4: no unrestrictable superuser as the normal admin identity.
  - Administrative capability is granted through the same ACL system as
    everyone else, and is itself subject to deny rules and audit.
  - A break-glass identity exists but is: offline by default, requires
    hardware (YubiHSM) to activate, every use is logged, and it cannot
    be the standing day-to-day admin.
  - No identity is exempt from audit. Power is grantable and revocable,
    never inherent and invisible.

- **rootdn naming drift (cn=Manager vs cn=admin).** The superuser is
  whatever DN rootdn names; it is not a fixed identity. OpenLDAP docs
  use cn=Manager, Debian uses cn=admin, others differ. Same role, no
  canonical spelling, so every deployment's break-glass DN is different
  and cross-references (docs, playbooks, runbooks) silently mismatch.

  ldap4: the break-glass role has ONE canonical name across all
  deployments. Not a per-distro convention, not a free-text rootdn
  string each admin invents. The name is part of the spec, so a runbook
  written for one install applies to every install.

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


- **group ACL restates schema per rule.** slapd's by group/OC/attr=
    requires naming the group's objectClass and membership attribute in
    every rule (groupOfNames/member vs groupOfUniqueNames/uniqueMember),
    because the server will not infer them. The most common authz
    primitive carries schema plumbing in every line.

    ldap4: group is a mandatory core kind with ONE fixed membership
    representation defined by the schema. The server resolves membership
    itself. Rules name only the group:
      grant write to <target> for group "cn=admins"
    No objectClass, no membership-attribute, no per-rule schema. Nailing
    the mandatory core schema is precisely what lets the server be
    schema-aware instead of making every ACL respell it.


## Access control engine

ldap4 authorization is a defined subsystem, not per-rule config
interpretation. Components:

- Rule store: ACLs are DIT entries, managed via ldapctl acl.
- Compiler: on rule write, evaluates the full rule set (deny-wins,
  recursive) into a materialized effective-permission set per
  (identity, scope). No first-match, no ordering.
- Hot path: request-time check is a bitmask AND against the
  materialized set. No rule walk.
- Invalidation: rule/group/entry changes recompute affected scopes.
- Introspection: explain (why this decision) and lint (dead/shadowed
  rules) are first-class operations.
- Inputs are identity and group (schema-resolved); network origin is a
  coarse pre-filter, never a standalone grant.

- **peername.ip takes one address; sets require regex.** slapd's ip
  style parses a single IP + optional %mask + :port, no list separator.
  Matching an arbitrary set of addresses forces peername.regex against
  the raw "IP=addr:port" string, i.e. pattern-matching a stringified
  address, fragile and opaque.

  ldap4: network match is a first-class list of CIDRs (and optional
  port constraints), not a string regex.
    from 10.10.10.10, 1.1.1.1, 10.40.0.0/24
  - Values are structured CIDRs, validated at write time.
  - No %mask vs /prefix inconsistency: CIDR /prefix only.
  - No regex-on-stringified-IP. If you need a set, you list the set.
  - Remains a coarse pre-filter under authentication, never a grant.

ldap4 network match accepts, in one list:
    - single address:   10.10.10.10
    - CIDR:             10.40.0.0/24
    - inclusive range:  10.10.10.1-100   (last octet) or
                        10.10.10.1-10.10.10.100  (full form)
  e.g.  from 10.10.10.10, 10.40.0.0/24, 10.10.10.1-100

Range rules:
  - short form varies the LAST octet only: 10.10.10.1-100
  - any wider range uses full form: 10.10.1.0-10.10.2.255
  - validated and normalized at write time; start <= end enforced

- **domain= (strict, ldap4-retained).**
  - Write/lint time: reject CNAME values. ldapctl acl lint resolves the
    domain= value; if it is a CNAME, error and name the canonical
    A-record target. Rule must use the A-record name.
  - Request time: forward-confirmed reverse DNS (FCrDNS). Reverse-resolve
    client IP to PTR, forward-resolve PTR back, require match. On
    mismatch, deny and log loudly:
    "domain= rejected: PTR <name> does not forward-confirm to <ip>".
  - Still never a standalone grant: layered under authentication. A
    confirmed hostname is still not an identity.

- **Authentication strength is global and maximal, not per-rule.** slapd
  splits this: TLSVerifyClient is global, ACLs cannot require a cert per
  target, and network specifiers (domain=, peername=) are offered
  without any auth guarantee behind them. ldap4 inverts it: the auth
  floor is global, mandatory, and maxed (TLS 1.3, mutual client cert
  required for every connection, no exceptions). There is no per-target
  auth-strength setting because there is nothing to tune: every
  connection is already cert-authenticated. Specifiers like domain= are
  available as coarse filters precisely because the global floor already
  guarantees a verified client. No cert, no connection: end of story.

- **Authentication strength: global, with a capability cost for
  lowering it.** Default and recommended: global maximal auth (TLS 1.3,
  mandatory mutual client cert, every connection). This is the only
  mode in which the full feature set is available, network specifiers
  (domain=, peername=), sensitive-attribute access, write operations,
  proxy authz, cross-realm.

  Lowering the floor is possible but degrades capability, not just
  security posture:
  - no client cert  -> no domain=/peername= grants, no EXTERNAL, no
    write, read limited to non-sensitive attributes
  - weaker/older TLS -> refused outright (TLS 1.3 is the hard minimum)

  The point: security is not a checkbox you disable for convenience.
  Turn it down and the server visibly withholds the bells and whistles
  that depend on knowing who you are. Capability is a function of
  proven identity.


- **Relationships are first-class and precomputed.** ldap4 supports
  relational queries (membership, manager chains, department joins,
  group ownership) but does not make admins hand-write joins per rule.
  Named relationships are materialized: resolved when the underlying
  data changes, stored, and tested on the hot path as a lookup, not a
  live join. Same model as materialized ACLs. Invalidation on
  member/attribute change is the hard part (shared with the ACL engine).

- **Relationship traversal belongs in the engine, not ACL syntax.**
  set= exposes DN/attribute traversal (this/ou, manager chains) as an
  inline set-algebra language the admin hand-writes per rule. These are
  directory relationships the server already holds. ldap4 resolves them
  as first-class, materialized relationships (membership, manager chain,
  ownership); the admin names the relationship, the engine walks it. No
  per-rule set math.

- **No config file for the ACL/relationship engine.** slapd's ACLs live
  in slapd.conf (or cn=config) and a reload/restart applies them. ldap4:
  the engine ships preconfigured with the mandatory safe core; changes
  are made online via ldapctl acl, applied live, no file to edit, no
  server downtime. Rule writes recompute affected materialized scopes in
  place. Config-file authorization is a leftover of static, restart-time
  policy.

- **set= is undocumented and dropped.** slapd's own slapd.access man
  page does not document set=; the only reference is an OpenLDAP FAQ
  page. A feature too obscure to document but complex enough to need its
  own article. ldap4: no set=. Everything it did (membership, same-OU,
  attribute existence/value, relationship traversal) is covered by
  first-class materialized relationships and predicates.

## Design note: scale-out provisions in a single-org core

ldap4 v1 targets a single organization of roughly 1000 people: one
suffix, one storage unit, one replication policy. Behemoth-scale
features (multi-tenancy, sharding, per-tree replication) are out of
scope for v1 but must remain reachable without redesign. Two
provisions are load-bearing and must be in the core now; everything
else is additive later.

### 1. Namespace/database decoupling

The mapping from DIT subtree to storage unit is a first-class
concept in the data model and config schema, even though v1 ships
with exactly one storage unit.

Rationale: multi-tenancy, delegated administration boundaries and
per-tree replication policies all hang off this abstraction. If ACL
materialization, config schema or tooling assume a single global
tree, that assumption spreads through every subsystem and cannot be
removed later.

Rule: no component may assume suffix == server == storage unit.
Components address a named storage unit; the resolver maps subtree
to storage unit. v1 ships with a resolver that always returns the
single unit.

### 2. Replication metadata reserved from day one

Replication itself is not implemented in v1, but the data model
records what any future sync mechanism needs:

- per-entry change sequence value (CSN equivalent)
- per-storage-unit high-water mark (context sequence)

Rationale: bolting change tracking onto a store that never recorded
it is the retrofit that hurts. OpenLDAP carries the scars: entryCSN
and contextCSN were grafted on after the fact. Recording sequence
metadata is cheap at write time and impossible to reconstruct
retroactively.

### Explicitly deferred (safe because 1 and 2 exist)

- proxy and meta backends
- per-tree overlay stacks
- horizontal sharding
- multi-provider replication topologies

These are additive: they consume the subtree-to-storage-unit
resolver and the change sequence metadata but require no changes to
either.

### Principle

Opinionated mandatory core with extension points. The extension
points above are load-bearing walls placed at construction time,
not doors cut into concrete later.

### Addendum: replication is an adopted problem, not a designed one

Replication mechanics are a solved problem. ldap4 will not design
consensus, conflict resolution or sync protocols. When replication
lands, it adopts an existing model: Raft or equivalent for the
config plane, eventual consistency with CSN-based last-writer-wins
for entry data, or whatever the state of the art is at
implementation time.

The reservation in provision 2 exists solely to keep that adoption
possible. Every off-the-shelf replication model consumes per-entry
change sequence metadata; none can reconstruct it from a store that
never recorded it. ldap4 records the metadata now and defers the
mechanism entirely.

Clarification on provision 1: the subtree-to-storage-unit resolver
is not server internals. The mapping leaks into the protocol and
admin surface: delegation boundaries, ldapctl addressing, ACL
materialization scope, export/import units. It is API design.
Internals behind the resolver stay swappable; without the resolver
the single-tree assumption becomes protocol-visible and permanent.


## Design note: anonymous-bind bridge for legacy applications

### Problem

ldap4 mandates authenticated access: anonymous bind is off by
default and the global-maximal-auth-floor rule requires proven
identity for every capability. Some legacy applications cannot
authenticate: they speak LDAP but only support anonymous binds and
cannot be patched. The common workaround, enabling anonymous access
server-wide for one application's benefit, destroys the auth floor
for everyone.

### Solution

A per-application bridge process: `ldap4-bridge`. One instance per
legacy application, never shared.

- Invocation: `ldap4-bridge --app <name> --conf
  /etc/ldap4/bridges/<name>.conf`
- Listens only where the target application can reach it: an
  `ldapi://` socket guarded by filesystem permissions, or a
  localhost port confined by network namespace
- Accepts the application's anonymous bind locally
- Forwards all operations upstream authenticated as a dedicated
  service identity: `cn=bridge-<name>,ou=services,...`
- The service identity is a real DIT entry subject to schema
  validation, per the existing rule that any DN used for
  authentication must exist in the DIT
- Upstream credential is a client certificate issued by the
  internal CA (step-ca phase); no passwords on disk
- ACLs on the service identity grant exactly the read scope the
  application requires and nothing else

### Properties

- The server never sees an anonymous bind. Anonymity terminates at
  the shim.
- Blast radius of each legacy application is its bridge identity's
  ACL scope.
- Every exception to the auth floor is enumerated, named and
  auditable: one bridge, one config file, one service DN per
  application. No blanket "allow anon because one app needs it".
- Removing a legacy application means deleting one bridge and one
  DIT entry.

### Non-goals

- The bridge is not a general proxy, load balancer or protocol
  translator. One app, one identity, read-scoped.
- The bridge does not attempt to add authentication to the legacy
  application. It contains the damage; it does not fix the app.

### Precedent

Equivalent to a dedicated slapd instance running back-ldap with
idassert-bind, or stunnel abuse patterns in the wild. ldap4 makes
the workaround a first-class, opinionated escape hatch instead of
an undocumented hack.

### Addendum: per-app credential and observed-minimum ACLs

**Credential naming.** The bridge's upstream client certificate is
issued to the application's identity and no other: subject bound to
`cn=bridge-<name>,ou=services,...`, one certificate per bridge, no
sharing and no wildcard service credentials. Revoking the
certificate kills exactly one application's access.

**Audit mode.** The bridge records every operation the application
performs: operation type, search base, scope, filter attributes,
requested attributes, written attributes. Because the bridge is the
application's only path to the directory, the recorded set is
complete by construction.

**Observed-minimum ACLs.** From the audit log the bridge emits the
minimal ACL covering observed behavior:
`ldap4-bridge --app <name> --emit-acl`. Deployment lifecycle:

1. New bridge starts in observe mode: permissive scope, full
   recording
2. After a representative period, emit the observed-minimum ACL
3. Apply it and switch the bridge to enforce mode
4. Anything outside the observed set is thereafter denied and
   logged, which either catches the application misbehaving or
   flags a legitimate new need for explicit review

Least privilege is derived from evidence, not guessed from vendor
documentation. The audit log is also the migration artifact: when
the legacy application is finally replaced, the log states exactly
what its successor must be able to do.

## Design note: tenant isolation

Applies when one deployment hosts directory trees for multiple
organizations. Single-org deployments run one tenant and none of
this costs them anything.

### Principle

Isolation is structural, not disciplinary. In OpenLDAP, multiple
databases share one process and the only walls between tenants are
ACL correctness and rootdn scoping: one misconfigured global ACL or
an overlay in the wrong stanza leaks across tenants. Humans get
that wrong. ldap4 does not rely on configuration discipline for
tenant boundaries.

### Logical isolation (storage-unit layer)

Tenant boundaries are a property of the storage-unit abstraction
(see: scale-out provisions, provision 1):

- One storage unit per tenant. Hard boundary: no cross-unit search,
  no cross-tenant referrals unless explicitly configured
- Per-unit everything: administrative identity (rootdn equivalent),
  ACL set, schema extensions, export/import scope, quotas, audit
  log
- No global superuser that spans tenants silently. Cross-tenant
  administration is a named, logged capability
- A search with a base above any tenant suffix fails or returns
  nothing. It never aggregates tenants

### Process isolation (kernel layer)

One ldap4d process per storage unit. The kernel is the isolation
boundary, not application code:

- systemd instantiated units: `ldap4d@<tenant>.service`
- Per-unit cgroup: tenant CPU, memory and IO quotas are systemd
  directives, not application code
- SELinux: shared type, distinct MCS category per instance, so
  same-binary processes cannot touch each other's files or sockets
- Separate database files, sockets and certificates per tenant
- A thin front router exists only if tenants must share one
  address; otherwise SNI or per-tenant addresses and no shared
  component at all

A memory-safety bug or parser exploit in one tenant's process
cannot read another tenant's data. No amount of in-process ACL
correctness provides that property.

### Consequence for server internals

The server code is never tenant-aware. Multi-tenancy is a
deployment pattern: the subtree-to-storage-unit resolver plus
process-per-unit orchestration. Non-traversal between tenants is
free because no process can see two tenants.

### Cost

N processes instead of one, no shared cache, cross-tenant
administration becomes an orchestration action. Trivial for
directory workloads.

### Cross-tenant references

When tenants legitimately need to see each other's data, isolation
becomes federation. Federation is explicit, named and owner-
controlled. Three mechanisms, in order of preference:

1. **Referrals.** Tenant A's entry points at tenant B's server
   (`ref: ldaps://...`). The client chases the referral and
   authenticates to B under B's rules. A never holds B's data; B's
   ACLs decide everything. Cost: client-side complexity; many
   legacy applications do not chase referrals.

2. **Explicit proxy mount.** A named subtree in A (e.g.
   `ou=partners,...`) backed by a proxy forward to B, using a
   service identity that B issued and B's ACLs scope. Transparent
   to clients. This is the bridge pattern pointed sideways: the
   cross-reference is enumerated, named, auditable and revocable by
   B unilaterally.

3. **Shared third tree.** Both tenants reference a common storage
   unit that neither owns, for genuinely mutual data such as a
   shared contacts tree.

Never permitted:

- Direct cross-unit reads inside the server: reopens the hole the
  process model closes
- Replicating one tenant's subtree into another: creates a stale
  copy outside the owner's control

Rule: cross-tenant visibility is always granted by the data owner,
scoped by the owner's ACLs, through a named channel the owner can
kill. Consent flows from the owner; it is never configured into the
consumer.

That framing, "sovereign directory domains with explicit trust, for Linux,"
is also the first honest marketing sentence ldap4 has. Note it somewhere.

## Design note: policy layer (Linux GPO equivalent)

Out of scope for the directory itself; documented here because the
directory is the policy store and the tenant model defines policy
scope. Separate product, post-v1 by a long margin.

### What Windows GPO actually is

Policy objects stored in the directory; a client agent pulls the
policies applying to a machine or user, computes precedence (local
→ site → domain → OU, with inheritance and overrides), and applies
them. The storage, retrieval and precedence machinery translates
directly to ldap4. The application machinery does not: Windows has
one configuration surface (the registry); Linux has dconf, sshd
config, sudoers, PAM, NetworkManager, firewalld and a hundred
other formats, each with its own ownership semantics and reload
behavior. Building typed backends for each is an ecosystem and
eternal maintenance, which is why FreeIPA stopped at HBAC/sudo/
SELinux maps and why Puppet/Ansible won general configuration.

### Decision: compile to Ansible, build no backends

The policy layer does only what Ansible cannot, and delegates to
Ansible everything Ansible already owns.

The policy layer provides:

- Policy objects stored in the tenant tree, typed and
  schema-validated. This is what raw Ansible lacks: a central typed
  policy store
- Precedence resolution: local → tenant → OU, inheritance,
  overrides, producing one resolved policy per host or user
- Kerberos-authenticated policy retrieval scoped by machine
  identity
- A compiler from resolved policy to an Ansible play

Ansible provides:

- Every configuration format on Linux, via 20 years of modules
- Idempotence, drift correction, reload semantics
- The apply loop: ansible-pull on a timer against the compiled
  policy. No agent to write

### Scope discipline

- No typed backends are ever written. If a setting has no clean
  Ansible module, the escape hatch is a policy payload that ships a
  raw play, marked as such
- The gap being filled is the compiler and the precedence model,
  not the appliers

### Team estimate

Directory-side policy store, precedence resolver and compiler: one
to two programmers, not a third team. The earlier three-team
estimate assumed handwritten backends; compiling to Ansible deletes
that work.

### Product sentence

Group Policy where the directory decides and Ansible applies.

## Design note: merge preflight (ldapctl merge plan)

### Problem

Bringing two tenants together (merger, consolidation) fails on
collisions that are invisible until something breaks: duplicate
uids, overlapping mail domains, conflicting schema extensions,
same-name groups with different members, policy rules touching the
same resource.

### Decision

Merging is never a blind import. `ldapctl merge plan <tenant-a>
<tenant-b>` produces a full conflict report before anything is
written:

- identity collisions: uid, uidNumber/gidNumber (should be empty
  under slice allocation), mail, principal names
- schema extension diff: additions, incompatible redefinitions of
  the same attribute or objectClass (the shared opinionated core
  guarantees the diff surface is only the extension layer)
- group and policy objects with colliding names or overlapping
  targets

Each conflict is presented with resolution options (rename, remap,
keep-both-under-tenant-prefix, defer). The admin resolves; the
resolved plan is a reviewable artifact (JSON, diffable, goes in a
repo); `ldapctl merge apply <plan>` executes exactly the plan and
nothing else. Apply refuses to run if the tenants have changed
since the plan was generated (plan carries content hashes).

### Properties

- Nothing is written until every conflict has an explicit
  resolution
- The plan is the audit trail: what was renamed, what was merged,
  who decided
- Dry-run by construction: plan generation is read-only

### Precedent

The workflow is a merge request for directories: diff, review,
resolve, apply. Same reason git refuses to merge with unresolved
conflicts.

## Design note: interactive reconciliation, frozen artifact

Extends the merge preflight note. Applies to both tenant merges and
legacy imports (ldapimport reconciliation): same pipeline, two
customers.

### Principle

Interactivity belongs on the read-only side of the wall. The
interactive session produces a dead artifact; the tool that writes
is separate and dumb.

### Workflow

1. `ldapctl merge plan` / `ldapimport analyze` produce the conflict
   and violation report as structured data
2. The report can be rendered as an interactive tree UI
   (self-contained HTML, schema-explorer pattern: no server, opens
   in a browser). Collapsible DIT, violation heat-coloring: core
   violations, remappable issues, clean subtrees
3. The admin resolves conflicts in the UI: per-entry decisions or
   batch rules ("remap all uidNumbers below 10000", "strip all
   jpegPhoto values")
4. Output is an artifact, never a write: the resolved LDIF plus the
   decision log (what was renamed, remapped, dropped, and by which
   rule)

### Two exits, both offline

- `ldapctl merge apply <plan>`: executes exactly the frozen
  artifact, guarded by content hashes of the source tenants;
  refuses if sources changed since analysis
- Take the resolved LDIF and load it manually into a fresh storage
  unit

### Rule

Apply consumes only the frozen artifact. No interactive session
ever holds a write handle to a storage unit. This keeps the
hammer-it-out-quickly UI completely separated from the change
window: review the LDIF, diff it, commit it to a repo, apply cold.

### Status

The UI is tooling, not architecture. The architectural commitment
is only: plan artifacts are renderable and editable offline, and
apply is artifact-driven with source-hash guards.

### Addendum: tenant provisioning is a privileged, atomic action

OpenLDAP inherits a layering gap: slapd runs unprivileged by
design, so it cannot create its own database directories, set
ownership or apply SELinux contexts. Packagers cover the first
database; every additional database is manual mkdir, chown and
restorecon, and the failure mode on a wrong-permission directory
is a startup error at best.

ldap4 resolves this structurally. `ldap4ctl tenant create` is a
privileged orchestration action, distinct from the unprivileged
ldap4d runtime, and provisions in one atomic step:

- storage directory with correct ownership and mode
- SELinux fcontext and the tenant's MCS category
- systemd instantiated unit (`ldap4d@<tenant>.service`) with
  cgroup quotas
- tenant slice for uidNumber/gidNumber allocation
- initial storage unit and administrative identity

Either the tenant is fully provisioned or nothing was created.
The daemon never needs privilege; privilege lives only in the
provisioning path, where it belongs. No tenant ever starts on a
half-prepared filesystem.

## Design note: bulk loading, online-first

### Principle

The online path must be fast enough that offline import is only
for disaster recovery. Slow online adds are a protocol-era
artifact, not physics: one synchronous round-trip and one
fsync-backed transaction per entry is what makes ldapadd take
hours. Full validation costs microseconds per entry; transaction
granularity is what costs hours.

### Online bulk: ldapctl add --bulk

Streams LDIF through the live ldap4d instance:

- entries grouped thousands per transaction instead of one
  transaction per entry
- full stack retained: schema validation, ACL evaluation,
  materialized constraint checks. Nothing is bypassed
- index maintenance deferred and built at end of stream where the
  storage engine allows it
- target: within small constant factor of offline import speed

This is the normal path for mass imports, without exception, on
any running system.

### Offline import: ldapimport

ldapimport is a recovery and provisioning tool; it is not an
import path for running systems. It exists for exactly two cases,
both defined by the absence of a live server:

- disaster recovery: the storage unit is corrupted or the instance
  cannot start; restore happens against dead files
- initial provisioning: `tenant create` lays down a storage unit
  before its ldap4d instance has ever existed

Guard: ldapimport takes an exclusive flock on the storage unit and
refuses to run if the unit's ldap4d instance is running (and vice
versa: ldap4d takes the lock at startup). The OpenLDAP failure
mode, where slapadd against a live database silently corrupts it
and the warning lives in documentation prose, is structurally
impossible. Refusal is a hard error with a human-readable reason,
per the error-strings principle.

### Rule

If an operator reaches for offline import to work around online
speed, that is a performance bug in the online path, not a
workflow. One tool per trust boundary: ldapctl speaks protocol to
the living; ldapimport touches files of the dead.

## Design note: request governance (rate and concurrency limits)

### Problem

slapd has almost no semantic rate limiting: conn_max_pending caps
queued operations per connection, thread pools bound global
concurrency, and the limits directive governs size/time per
identity, but nothing limits operations per second or concurrent
operations per identity across connections. The standard deployment
compensates with a firewall, which sees TLS streams, not LDAP
operations: it cannot know that one authenticated identity opened
three connections and is pumping ten thousand searches through
them. Per-identity governance only exists where the identity
exists: inside the server, after the bind.

### Layering

Every layer guards its own boundary:

- network layer (firewall, nftables, SRX-class gear): SYN floods,
  connection rate per source address, L3/L4 noise. Recommended in
  front, out of scope for ldap4
- server layer (ldap4d): everything requiring knowledge of the
  authenticated identity or the operation

### Mandatory per-identity limits

All requests are authenticated (no anonymous operations exist), so
every request has a name attached. Per identity, mandatory, with
sane defaults:

- concurrent in-flight operations, counted across all of the
  identity's connections
- operation rate (ops/second, token bucket or equivalent)
- existing size and time limits fold into the same mechanism

Overrides per identity or group through the same limits machinery
that serves enumerated heavy consumers (bulk readers, sync
services). Unlimited is not expressible, consistent with the
timelimit rule: overrides raise ceilings, they do not remove them.

### Interaction with client-requested timelimit

Client-requested limits only shrink within the server ceiling and
are innocent by construction: a flood of 1-second requests is
cheaper for the server than the same flood at the ceiling. Floods
are owned by this note's rate limits, not by the timelimit field.

### Breach as signal

Limit breaches are structured security events, not just refusals:
identity, limit, observed value, source. An identity whose baseline
is three queries a minute suddenly running thousands a second is a
stolen credential or a broken deployment; the governance layer is
also the detection layer. This feeds the same observed-baseline
philosophy as the bridge audit mode.

### Failure semantics

Refusals are polite and typed: busy/rate-exceeded result with a
human-readable reason and, where sane, a retry-after hint. Clients
under limit never queue behind clients over it.

### Addendum: client-side default for requested limits

The protocol allows clients to request limits lower than the
server ceiling, never higher. ldap4's own clients (ldapctl,
libldap4) send no requested limit by default: the server ceiling
applies. The flag exists, documented in the man page, for callers
with a real deadline. Dumb by default, expressive when needed.

## Design note: filter planner seam

Filter execution sits behind a planner interface from v1. The seam
is between parse and execute; nothing else may call execution
directly.

v1 planner is deliberately dumb: walk the filter, check index
availability per term, order terms naively, and classify the query
as indexed, partial or full-scan. No cost model.

The classification is the immediate payoff:

- rate-limit weighting: scan-class operations consume more of an
  identity's budget than indexed point lookups
- audit signal: an identity whose baseline is indexed lookups
  suddenly issuing scan-class filters is flagged
- `ldapctl explain <filter>`: shows the classification and which
  terms lack index support, mirroring acl explain

Cost-based planning, if ever justified, replaces the planner
behind the same interface. Directory workloads are read-heavy
point lookups; the expectation is that classification-only lasts
indefinitely.

ACLs need no equivalent seam: materialized deny-wins evaluation
with precomputed bitmasks is already an ahead-of-time plan, with
acl explain and acl lint as its inspection surface.

### Addendum: planner as sensor

Planner classifications and limit events are exported as labeled
metrics (Prometheus format): operation counts by class, identity,
tenant; rate-budget consumption; breach events. The metrics
endpoint is a named, authenticated consumer like any other.

Three uses fall out of one classification stream:

1. Indexing error detection: recurring scan-class filters on the
   same attribute indicate a missing index. The planner aggregates
   and recommends: "attribute department caused 40k scans this
   week; add eq index." acl lint philosophy applied to indexing.
2. Baseline deviation: rolling averages per identity, tenant and
   class; alert on departure. Granularity is label depth.
3. Capacity truth: class mix over time shows what the workload
   actually is versus what was indexed for.

The planner is not just an execution step; it is the sensor that
makes indexing empirical. Third instance of the evidence-over-
guesswork pattern, after observed-minimum ACLs and bridge audit
mode.

## Design note: timelimit is execution time, not a deadline

The operation timer starts when a worker begins executing, not
when the request arrives. Queue wait on a saturated server does
not consume the client's time budget. Consequence: timelimit is
not an end-to-end deadline, and the protocol documentation states
this explicitly rather than leaving it as folklore (OpenLDAP
behaves the same way but buries it).

Metrics consequence: queue-wait and execution time are exported as
separate labeled measurements per operation class. If only total
or execution time is exported, saturation hides inside
apparently-fast queries: a server at capacity shows healthy
execution times while clients experience multi-second latency.
Queue-wait percentile panels are the saturation indicator.

Clients needing a true end-to-end deadline enforce it client-side;
the requested-limit field bounds execution only.


## Design note: read-only is storage state, no privileged opcodes

### Read-only

Read-only is a property of the storage unit, enforced at the write
path, not an operation-level gate. Any operation reaching the
write path of a read-only unit fails, regardless of opcode.
OpenLDAP's readonly directive gates the modify operation while the
Password Modify extended operation walks past it (book, p235):
an operation-level gate protecting a data-level invariant. ldap4
does not reproduce the pattern.

### No extended operations

LDAPv3 extended operations (OID-addressed opaque payloads) are
removed. Their failure mode was not extensibility but bypass:
extensions arrived as blobs outside the semantics the core
enforces. ldap4 rule: every operation goes through the same
pipeline: authentication, ACL evaluation, limits, write path,
replication metadata. No opcode is special. Operations that
LDAPv3 shipped as extensions and ldap4 actually needs (whoami,
cancel) are core operations. New operations arrive only by
protocol version, never by side channel.

## Design note: replication topology, single writer

One writer per storage unit, N read replicas. Active-active is
rejected: directory workloads are overwhelmingly reads, multi-
master buys write availability at the cost of conflict resolution
and silent divergence (OpenLDAP's CSN last-writer-wins can eat
writes), and minutes of write unavailability during failover is
nothing for directory write volumes. Silent conflicts are
corruption; downtime is an inconvenience.

Failover:

- v1: operator-promoted, one guarded command.
  `ldap4ctl replica promote <host>`: fences the old provider
  (refuses writes if reachable), verifies the candidate holds the
  highest CSN among reachable replicas, flips roles, repoints the
  remaining replicas. Scriptable, atomic-ish, no hand-edited
  configs. A runbook of manual steps is how split-brain happens at
  03:00; one guarded command is safe indefinitely.
- v2: Raft-elected promotion behind the same semantics. The v1
  command becomes the manual override.

Reads load-balance trivially: replicas are consistent or lagging,
never divergent.

### Addendum: substring index default

Default sub indexing covers prefix and suffix (forward plus
reversed-string index): both directions cheap to serve, cost is
one extra index, admin never picks subinitial/subfinal. Interior
matching (subany equivalent, n-gram based) is opt-in per
attribute: highest write and space cost, rarest legitimate query
shape; the planner flags scan-class interior-wildcard filters
when a deployment needs it. Cost decisions surface through
measurement, never through hand-tuned variant selection.

## Design note: online index builds

Index changes are online operations. slapd requires offline
slapindex to build newly declared indexes over existing entries;
ldap4 does not reproduce this.

`ldapctl index add <attr> <type>` starts a background build over
existing entries. Concurrent writes dual-write into the building
index. The planner treats the attribute as unindexed (scan class)
until the build completes and flips to ready; queries never see a
partial index. Build status is visible via `ldapctl index status`;
builds are resumable after restart. `ldapctl index drop` is
immediate.

Same shape as PostgreSQL CREATE INDEX CONCURRENTLY: solved
problem, adopted not designed. Consistent with online-first bulk
loading: no offline step exists for a running system.

## Design note: no -q flag, provenance decides validation

slapindex/slapadd -q skips consistency checking as an operator
flag: go-faster bravado with corruption risk in a man-page
subordinate clause. ldap4 has no equivalent flag. Validation is
never skippable by assertion; what changes is what needs
validating, and that is decided by evidence:

- ldapexport artifacts carry a manifest: content hashes, entry
  count, schema version. ldapimport of a manifest-bearing artifact
  verifies integrity against the manifest: cryptographic, cheap,
  no per-entry re-derivation of what the exporting server already
  guaranteed
- foreign LDIF (no manifest, or manifest fails) gets the full
  validation pipeline: schema, constraints, referential checks.
  Not disableable

Trusted fast path is earned by provenance, never claimed by flag.
The restore-speed use case -q served is covered by the manifest
path at full safety.

## Design note: invariants are core, extension points are for behavior

The overlay mechanism (OpenLDAP 2.2) was sound architecture: an
interception pipeline letting features ship independently instead
of bloating the monolith. The mistake was what got shipped as
overlays: referential integrity (refint) and uniqueness (unique)
are database invariants, Codd-era table stakes, and slapd made
them opt-in plugins, default off, stackable in the wrong order.
Correctness became an accessory.

ldap4 keeps the pipeline (every operation through the same stack:
see no-privileged-opcodes note) and draws the line:

- invariants are core, always on, not configurable off:
  referential integrity, uniqueness constraints, schema validity
- extension points are for behavior: logging, sync, rewriting,
  metrics. Nothing plugged into the pipeline can weaken an
  invariant; extensions observe and transform, they do not gate
  correctness

A deployment where entries can dangle or duplicate is not a
configuration; it is a bug the operator was allowed to write.
