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

ldap4 resolves this structurally. `ldapctl tenant create` is a
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
  `ldapctl replica promote <host>`: fences the old provider
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

## Design note: change feed, one mechanism, two consumers

Adopted from slapo-accesslog, promoted from overlay to core. The
directory maintains an ordered, structured record of mutations:
who, what, when, attribute-level detail (add/delete/replace per
value), result. Records are schema-typed and queryable through the
protocol like any data, subject to ACLs: no shell access needed to
read the trail.

One mechanism, two consumers:

- human: audit. `ldapctl log query` with filters (by DN subtree,
  identity, operation type, time range), indexed like anything
  else
- machine: replication. Replicas consume the same records as
  replay instructions (delta replication: ship the change, not the
  entry). Rides the provision-2 CSN metadata

Being core, not optional: the feed cannot be off, per the
invariants-are-core rule; audit that can be disabled is not audit.
Retention is policy (purge age per tenant), existence is not.

Cost acknowledged: every write amplifies into the feed. Feed
storage is a separate region of the storage unit with its own
purge policy, so audit volume never competes with entry data.

## Design note: two-phase migration, core before extensions

Site extensions are the wild west: every deployment bolts on its
own attributes, and migrations die in the bolt-on layer, not the
core. ldap4 makes the layers separable at export, visible at diff
and sequential at import.

### Provenance-split export

Every attribute value is typed by provenance: core schema or a
named extension (see: core/extension schema separation). Export
honors the split:

- `ldapexport --core-only`: the tenant stripped to the
  guaranteed-portable subset. Loads into any ldap4 deployment by
  construction
- `ldapexport --extensions`: the bolt-on payload as a separate
  labeled artifact: extension schema definitions plus the values
  they own, per extension

### Two-phase import

Phase 1: import the core artifact. Identities, groups, the DIT
skeleton: everything the opinionated core guarantees. The tenant
is functional at the end of phase 1.

Phase 2: import extension artifacts, one extension at a time, each
through the reconciliation pipeline (analyze, conflict report,
frozen plan, apply). A failing extension blocks only itself:
phase 1 is never held hostage by someone's 2009 custom
objectClass.

### Diff shows the layers

The interactive reconciliation tree renders provenance visibly:
core subtree structure in one visual register, extension-owned
attributes and classes in another, per named extension. "What did
this company bolt on" is navigation, not archaeology; the migrant
sees exactly which layer each conflict lives in.

### Why

Migrations get a working directory on day one (core), then absorb
the wild west incrementally, with evidence, per extension. The
failure mode of legacy migrations: all-or-nothing imports dying
midway through someone's bolt-ons: is structurally excluded.

## Design note: RFC boundary blessed as the portability contract

The classification is official; the consequence is ours.

RFC 4512 defines mandatory system schema; RFC 4519 the standard
user schema; RFC 4524 (cosine), RFC 2798 (inetOrgPerson) and
RFC 2307 (NIS) complete the standards-defined inventory, with
IANA registries recording ownership of every name. ldap4 blesses
this exact set as the portability boundary:

- RFC-defined schema = the core. Guaranteed portable, phase 1 of
  any migration, the `--core-only` export surface
- everything else = named extension by definition, however old,
  however load-bearing (norEdu*, vendor schemas, site bolt-ons)

No standards body defined this consequence; the sets are theirs,
the contract is ours. For migration FROM OpenLDAP, the same
boundary applies without server enforcement: a splitter tool
classifies a slapcat export against the RFC inventory (static,
enumerable) and emits the two-artifact form the two-phase import
consumes. Legacy deployments get provenance data for free because
the RFC set is known and fixed.

ldap4's own core schema is a curated subset/refinement of the RFC
set (no-binary-blobs rule amends it, e.g. jpegPhoto to
jpegPhotoURL); deviations from RFC schema are themselves
enumerated in this document, so the delta between "RFC core" and
"ldap4 core" is a published list, not folklore.

## Design principle: compensating tooling is evidence of wrong defaults

Every wrapper, GUI, glue script and deployment framework that
exists to keep humans away from a server's native configuration
is a measurement of that configuration's wrongness. Nobody builds
compensation for correct behavior. FreeIPA is the proof case: an
entire product category (389 DS + Kerberos + web UI + certmonger
+ glue) whose function is wrapping directory-era defaults so no
operator touches them. Every slapd Ansible role, this project's
included, is the same evidence at smaller scale.

ldap4 fixes the default instead of shipping the wrapper. Applied
instances already in this document: no anonymous-bind toggle, no
unlimited limits, no -q validation bypass, no substring-variant
hand-tuning, no offline index builds, provisioning as one atomic
privileged action. Each deletes a knob some wrapper would
otherwise exist to hide.

Test for every future knob: if the imagined deployment guide
would say "always set this to X", the knob is a bug: ship X.
ldapctl stays thin because the server needs no compensation. The
day someone builds a simplification layer over ldap4, that layer
is a bug report. 

ldapctl carries no logic a reimplementation would have to copy:
parse, one call, render. The server owns every decision; a weekend
clone in another language is the acceptance test.


## Design note: authentication ladder, passwords are a ramp not a floor

v4's destination is Kerberos-only. All authentication, including
second factors, happens at the KDC (OTP via FAST pre-auth,
RFC 6560; hardware keys via PKINIT, RFC 4556); the directory never
sees a credential of any kind, only tickets. The directory's 2FA
story is: it has none, on purpose. That is the KDC's job and
krbctl's problem (parked with the Kerberos arc). Systems that bolt
second factors onto the directory bind path reintroduce
credentials exactly where this design evicted them.

The first iteration nonetheless accepts simple binds over the
mandatory TLS channel, because refusing them on day one refuses
every existing client. The ramp is explicit and mechanically
enforced:

- Phase 1 (initial releases): simple bind over TLS accepted.
  Passwords are verified against the KDC (passthrough), never
  stored in the directory: the no-passwords-in-DIT rule holds from
  day one; simple bind is a compatibility veneer over Kerberos
  verification
- Phase 2: simple bind accepted, deprecation warning in the bind
  response message and a counter in the metrics (identities still
  binding simple, per tenant: the sensor pattern; admins see
  exactly who has not migrated)
- Phase 3: simple bind refused by default, per-identity exception
  list (enumerated, expiring: same shape as the bridge: named
  legacy consumers, not a global toggle)
- Phase 4: the code path is removed

The phase is a server release property, not a config knob: no
deployment can elect to live in phase 1 forever, per the
compensating-tooling principle. Phase 2 metrics make phase 3
schedulable with evidence instead of guesswork.

### Addendum: weird-auth interception rule

Password-like binds over TLS are translated to KDC verification
and logged for extinction: the metrics name every identity and
mechanism still doing it. Challenge-response mechanisms (NTLM
relics, digest schemes, appliance HMAC dances) are untranslatable:
the server never possesses a verifiable secret, and faking the
exchange means a parallel credential store, which is the disease
returning through the side door. Those get a named bridge (scoped
identity, enumerated, expiring) or refusal. No parallel credential
store, ever.

The doorman line: weird auth never enters the building: bridge it
at the door or vaya con dios. The bridge exists so a shop with one
cursed appliance does not stay on ldap3 over its worst device.

## Design note: join state is server truth, status is a live probe

The Linux domain-join problem is not the joining; it is that join
STATE is a vibe. SSSD/realmd smear enrollment across five places
(keytab, sssd.conf, nsswitch.conf, PAM stack, krb5.conf) with no
single source of truth; "am I joined" means inspecting all five,
and realm list answers from its own cache, not from evidence. AD
solved this decades ago: the join is an object (machine account)
and Test-ComputerSecureChannel is a live probe against it.

ldap4 adopts that shape:

- Enrollment creates a machine entry in the DIT (per the rule that
  any DN used for authentication is a real entry). Joined = the
  entry exists AND the machine's keytab can authenticate as it.
  One truth, server-side, queryable
- `ldapctl client status` is a live probe, not a config reader: it
  performs real authentication with the machine credential and a
  real lookup through the enrolled path, reporting green/red per
  layer with human-readable reasons (keytab/ticket, NSS
  resolution, PAM stack), exit code for scripts. The
  Test-ComputerSecureChannel of the system
- Enrollment mutates system files only as an explicit admin
  action, delegated to the distro switchboard (authselect or
  equivalent) with printed diff and native rollback; packages
  never touch auth config
- Directory and realm halves compose: the enroll verb performs the
  directory join and calls the realm tooling (krbctl) for the
  Kerberos half; each usable alone for exotic cases, one operator
  verb by default. A machine enrolled for lookup but not auth is a
  flagged, named state, not an accident

Because state lives server-side, the enrollment tool is thin (per
the thin-client principle) and CAN be a separate binary without
creating a second source of truth: the tool is an actor against
the DIT, never the keeper of join state.

## Design note: no result caching

ldap4 has no result cache, by principle:

- Storage reads are memory-speed by architecture (memory-mapped
  engine; the OS page cache is the cache). A result cache above
  the storage layer buys microseconds
- It costs the two hard problems caches carry: invalidation
  correctness, and ACL bypass risk: a cached result computed for
  identity A must never answer identity B, so the cache key must
  carry the full authorization context, at which point hit rates
  collapse and the machinery is a complicated way to be slightly
  wrong
- Slow reads have a correct fix: the planner classifies them, the
  metrics name the missing index, the index gets built online.
  Caching would mask the signal the sensor exists to produce

Staleness in identity data is a lie the server tells. If ldap4
ever gains a proxy role fronting another directory, caching there
is an explicit named component with declared TTLs and visible
staleness: never a default, never silent.

## Design note: one canonical config, commented out

ldap4 ships exactly one configuration file: every option present,
every option commented out, the default value stated inline in the
comment. There is no config library, no per-scenario templates, no
include directive.

Properties:

- An empty (or untouched) config file is a valid, fully functional
  server. Defaults are the documentation
- Every uncommented line is a visible, deliberate deviation from
  default. `diff` against the shipped file yields the deployment's
  complete list of deviations: the audit artifact for "what did
  this site change"
- Comments carry the reasoning, not just the syntax: what the
  option does, why the default is what it is, references where
  they exist (the slapd.conf-with-RFC-references habit,
  generalized)
- Adaptation is uncommenting, never authoring. Precedent:
  sshd_config commented-defaults style

Scenario documentation ships as commented walkthroughs (the
university, the AD-proxy shop, the multi-tenant host), each
showing the handful of lines that deviate from default and the
prose reasoning why only those. If any scenario requires more
than a screenful of uncommented lines, that scenario is a bug
report against the defaults, per the compensating-tooling
principle.

Schema is not config: the RFC set is compiled in, include does
not exist as a directive, and extensions arrive through
`ldapctl schema add`, typed and validated. The config file
configures the server; it never loads code or schema from paths.

# ldap4 Design Notes: Chapter 7 Harvest

Source: parking lot items 1-35, banked while reading "Mastering OpenLDAP"
chapter 7 (Multiple Directories), Parts 9 and 10, plus replication and
proxying material carried from Parts 7 and 8.

Organised thematically. Item numbers retained as anchors.

Provenance note: items 1-26 were banked during the Part 9 replication
reading. The full discussion text of that session is not retrievable from
past-chat search (the session is indexed as a summary covering only the
ppolicy pages), so those items are expanded here from the handoff headlines,
the recovered Part 7 and Part 8 material, and this session's continuations.
Where an item's expansion is reconstruction rather than recovered text, the
design intent is preserved; the exact original wording is not.

---

## 1. Framing

The recurring design smells in LDAP, NIS, NFS and Kerberos are not
independent mistakes. They are the seams left by a single 1980s
networked-Unix project that was federated into four separate standards by
hardware limits and inter-vendor politics: Sun against OSI against MIT.

Each of the four stores fragments meant for a neighbour. LDAP holds NFS
automount strings and NIS posixAccount numbers. RFC 2307 is NIS expressed
in LDAP. Kerberos assumes DNS and a directory. NFS trusts asserted uids.
The trust between them is unvalidated convention.

Removing those seams by unifying identity, authentication and directory
into one coherent system is the point of ldap4. Home directories and
mount points are facts the directory STATES, not configuration it STORES
(items 24 and 25 below are the concrete instances).

**Item 26: build method.** Clean-room from the RFCs. Own test suite.
slapd used as a black-box oracle for behavioural comparison, never as a
source of code.

---

## 2. Cluster model

**Item 1: one node class.** No masters, no slaves, no shadow servers, no
provider and consumer as node types. Every node runs the same binary. Role
is a runtime state, not an installation decision. The slapd world where a
consumer is configured differently from a provider, and converting one into
the other means editing configs on five boxes, does not exist here.

**Item 2: atomic cluster writes.** Writes are consensus-ordered across the
cluster. Raft. Not eventual convergence with conflict resolution bolted on,
and specifically not OpenLDAP's CSN last-writer-wins, which can silently eat
writes. The Part 7 position stands underneath this: directory workloads are
overwhelmingly reads; multi-master buys write availability at the cost of
silent divergence, and silent conflicts are corruption while write downtime
is an inconvenience. Consensus ordering is the multi-node form of the
single-writer principle.

**Item 7: node identity is not a replication user.** A node authenticates as
a node, with a node credential. It does not bind as `uid=replicator` the way
a syncrepl consumer does. Replication identity in slapd is an ordinary user
entry with extraordinary read rights and a `limits` exemption, which means
the most powerful read credential in the deployment is a password in a
config file. In ldap4 the replication channel rides node identity, which is
part of the cluster trust fabric rather than the user database.

**Item 23: three-layer identity.** Cluster UUID, node incarnation, node
credential. The cluster UUID says which cluster this is. The incarnation
says which instance of this node this is, so a rebuilt node is
distinguishable from its predecessor. The credential authenticates it.
Distinct concerns, never collapsed into one value.

**Item 19: lifecycle.** Staged cold start: nodes come up in a declared
order, not a thundering herd racing for election. Cascade fan-out for large
clusters: a joining node syncs from a nearby member, not necessarily the
leader, so a hundred joins do not serialise on one box. Genesis is asserted,
never inferred: the first node of a cluster is told it is genesis by the
operator; no node ever concludes from silence that it must be first, because
silence is what a partition looks like. No re-initialisation of an existing
node: destroy it and join a fresh one, so there is never a node whose
history is ambiguous.

**Item 22: no cluster-destroy verb.** A node can be destroyed:
`decommission` exists and the Ansible playbook for it is queued. The cluster
cannot be destroyed by a verb, because there is no single actor entitled to
that decision and no operational story that requires it. A cluster ends by
its last node being decommissioned, deliberately, one at a time.

**Item 16: learner nodes.** Join by snapshot plus tail: full state transfer
at a point in the log, then replay from that index. A learner replicates and
serves reads but does not vote, so a remote site can hold a node without
becoming a quorum liability. Admission of learners is DoS-hardened under
item 17: joining is a privileged operation, not an open door.

**Item 20: sharded consensus.** Many small consensus groups rather than one
large quorum. Election cost and message fan-out grow with voter count, so
big flat quorums are both slower and more fragile. Sharding is also the
lever if a branch site needs local writes: give the branch its own group for
the subtree it owns.

**v1 operational reality** (carried from Part 7, still true as the
transition plan). Before raft exists, promotion is operator-driven and
executes as one guarded command: fence the old provider so it refuses writes
if reachable, verify the candidate holds the highest log position among
reachable replicas, flip roles, repoint the remaining replicas. If the old
provider is unreachable, the operator is asserting "dead, not partitioned,"
and the command takes an explicit acknowledgment so the human owns the
split-brain risk. A runbook of manual steps is how split brain happens at
03:00; one guarded command is safe indefinitely. Raft automates the
decision; the v1 command survives as the manual override. Item 9's
promote and demote playbooks are the lab rehearsal of exactly this.

---

## 3. Liveness, partition and demotion

Items 17 and 31, merged. One failure detector with one policy threshold
drives both flap demotion and partition demotion. Not two mechanisms with
two sets of tunables. Item 11 already made liveness core rather than an
add-on; this is that core's specification.

**Core rule.** A node that cannot reach quorum demotes ITSELF to read-only.
It never demotes anyone else. Demotion of another node is a decision only a
side that already holds quorum may make, and the quorum side initiates
resync of returning nodes.

This is the property that prevents split brain. From ping failure alone a
node cannot distinguish a dead peer from an unreachable one, so a rule that
lets any node demote any other forks the cluster: each side demotes the
other and both keep writing.

**Flap demotion** (item 17's original half): a node that oscillates,
reachable then not then reachable, is demoted by the quorum side using the
same detector and threshold, because a flapping voter is worse than an
absent one. Rejoin follows the same resync path as partition recovery.

**Timing.** Election timeout in the 150-300ms range, the standard raft
band. Resync is a separate and much longer clock: minutes after a long
partition, because the returning node replays the log it missed. A returning
node does not vote until resync completes.

**Item 32: leader tiebreak.** The leader holds two votes to break stalemates
in even-sized voter sets. Scoped to tiebreaking only, not partition
handling: in a partition the minority cannot see the leader at all, so the
extra vote is irrelevant there. It also does nothing when the leader itself
is the node that died, which is the common trigger for elections, so it
reduces stalemates without removing the odd-voter-count recommendation.

**Placement is a correctness decision.** With two voters at headquarters and
three at branches, a link cut leaves the branches legitimately holding
majority and headquarters read-only. Raft does not know headquarters is
special. `ldapctl` lints for this: warn on even voter counts, and warn when
voter distribution across sites allows a branch to outvote the primary site.
If a site must always win, place the voters accordingly, or give it its own
consensus group under item 20. Site weight as an explicit policy layer above
raft is possible but is a deliberate later decision, not a default.

### Forced quorum override

An even split, four against four, leaves both sides read-only. That is the
correct outcome: total write outage, zero divergence, human decides. Failing
safe rather than failing available. The admin then needs a way to declare
one side authoritative, and that verb is dangerous enough to need ceremony,
because running it on both sides simultaneously is exactly how you get the
split brain the design just avoided.

`resync` is the wrong verb for this case: in a clean even split nothing is
out of sync, both sides hold identical logs. The verb is a forced quorum
override, distinct, with its own confirmation and a loud audit entry.

Ceremony required before the override takes effect:

- type a phrase stating the consequence, not "yes": a tired admin types yes
  without reading
- visual diff of cluster state and last log index, even in a TUI
- mandatory reason string written into the audit chain (the Windows Server
  shutdown-tracker pattern: mandatory on Server SKUs, reason plus comment
  into the event log, and it works because it forces a sentence rather than
  a click)
- forced countdown before effect, with a large visible warning
- two-person rule optional, deferred until the credential story exists
  (YubiKey presentation once Kerberos is in)

Two humans acting independently on two sides of a partition is an HR
problem, not a directory problem, and the design does not try to prevent it.
It survives it instead, which is what the ceremony's frequency reduction
plus the dual-marker rule below are for.

**Force markers.** A side that forces quorum writes a permanent hash-chained
record: which node, which human, which log index, what the state was. The
marker is evidence. It is never an arbiter.

**Dual force markers on rejoin.** Both sides go read-only. No automatic
merge. Plain-language log naming both sides, both operators and both
indices: "two forced quorums detected, side A forced by X at index N, side B
by Y at index M, writes suspended, do not merge, escalate." `ldapctl`
reports the divergence: how many entries differ, which subtrees, since which
index. No verb exists that silently discards one side's writes.

Timestamp arbitration is explicitly rejected. Clocks across a partition are
exactly what cannot be trusted: skew, NTP dead during the same event that
caused the partition, drifted VM clocks. Raft uses log indices and terms
rather than wall clock for this reason. Worse, both sides acknowledged
writes to clients as durable after forcing; automatic selection is data loss
by coin flip at the moment two humans have each already made a deliberate
decision. Reconciliation is the item 21 adopt-versus-merge machinery: a
human decision, a wizard, warnings.

The 3am answer is: read-only until daylight. Reads keep working throughout.
Sign-ins continue, the institute functions. Only writes wait for someone who
can decide which acknowledged writes get thrown away.

---

## 4. Replication and audit

**Item 5: anti-entropy.** Merkle tree comparison anchored at a log index,
git-style content addressing. Two nodes verify convergence by comparing
subtree hashes and descend only into branches that differ, so verification
cost scales with divergence rather than directory size. This is the
background correctness check that consensus ordering alone does not give
you: it catches disk-level divergence, bugs, and bit rot, not just missed
messages. Not CSN vector comparison.

**Item 6: hash-chained audit.** Each audit record carries the hash of its
predecessor, so the log is tamper-evident by construction: truncation or
modification breaks the chain visibly. The force markers in section 3 write
into this chain. The Part 8 decisions carry forward underneath: the log
store inherits the primary database's ACL, no secrets in logs, audit format
is core with mandatory actor, outcome and timestamps, and `ldapq` can replay
operations from audit records.

**Change feed as core.** Not an optional overlay. One mechanism serves
audit, delta replication and downstream consumers. This is the accesslog
plus delta-syncrepl idea from the book, promoted from clever overlay
composition to the native architecture: slapd got it right by accident, as
two overlays that happen to compose; ldap4 makes it the spine.

**Item 8: build order and strategy.** Syncrepl provider first. The strangler
pattern against slapd: ldap4's first deployable role is being the provider a
stock slapd consumer replicates from. Existing deployments point their
consumers at it, nothing on the consumer side changes, and the replacement
proceeds inward from there. This dictates build order: the sync protocol
surface comes before almost everything else, because it is the on-ramp.

**CSN as a compatibility shim.** CSNs exist only at the slapd-facing
boundary, generated for consumers that need them. Internally there are log
indices and terms. No internal concept depends on wall-clock-derived change
numbers.

**Item 15: bulk operations as wire primitives.** One transaction covering
many entries rather than one round trip per entry. This is simultaneously
the migration-speed lever, the write-throughput lever (write cost is fsync
latency and batching amortises it, section 15), and the reason
`ldapimport` can be fast without a side-door like slapadd that bypasses the
running server.

**Item 13: every node validates.** No node accepts data on the assumption
that an upstream already checked it. Replicated writes pass the same schema
validation as client writes. The slapd counterexample is slapadd loading
entries no ACL and no schema check ever saw; that class of side door does
not exist (Part 3 decision, reaffirmed).

**Item 3: no referral-as-signal.** Referrals as a replication and topology
mechanism are out: the updateref pattern, where a read-only replica answers
a write with "go ask that server over there," pushes topology knowledge into
every client and trusts them all to handle it correctly, which they do not.
Whether a referral-shaped mechanism exists at all for other purposes is
still open (the person flagged referrals as potentially useful and needing
thought); what is decided is that no core mechanism depends on clients
chasing them, and the router never punts to the client.

**Identity assertion by configuration does not exist** (carried from Part
7). slapd's chain overlay plus idassert lets a middle box tell the provider
"I am acting for uid=george" on its own authority: the provider never
authenticated george, it has the replica's word, and one compromised chain
credential can act as anyone it may assert. Kerberos solved the same
delegation need cryptographically with constrained delegation. In ldap4,
anything acting on a user's behalf carries a real delegation credential or
acts as its own named identity. The translucent proxy mode in section 7
operates within this rule.

**Item 4: discovery by DNS SRV**, not by referral chasing and not by
configured host lists. Same rule already adopted for Kerberos realm
discovery via `_kerberos._udp`: DNS must exist and be correct, a hard
prerequisite, same as AD.

---

## 5. Proxying, federation and namespace

**Item 27: one backend per service instance.** Multiple backends means
multiple service instances with separate configs, relaunched with a
different config to get a proxy or a secondary backend. This kills the
suffix-longest-match dispatcher inside one process, kills per-database
overlay scoping bugs, makes crash blast radius one backend, and matches the
process-per-tenant isolation model already adopted.

**Item 28: the router.** The cost of item 27 is that nobody gets a unified
namespace for free, and unified namespace is a requirement because
federation (forests and trees) is coming. So the router exists, and it is
designed now rather than retrofitted.

The router is an explicit service holding no data, only a namespace map of
prefix to backend service. Stateless: no election, no quorum, restart is
free, run as many as needed. It is deliberately NOT the raft leader. The
leader is elected for write ordering within one cluster; the router spans
backends that are different clusters, possibly different forests, and a
cross-forest namespace has no shared raft group to elect from. Tying routing
to an election also degrades routing whenever a backend is mid-election.
Different lifetimes, different failure modes. Keeping the namespace map
consistent across router instances is versioned config with a stale-map
error, not consensus.

Router behaviour, decided:

- writes crossing a namespace boundary route to the owner
- searches spanning backends: fail closed per item 29; any backend
  unreachable errors the whole search
- schema validation belongs to the backend: data on a node is that node's
  or cluster's responsibility (item 13 restated at the boundary)
- the router never punts to the client with a referral

**Process model.** Single shipped binary, role selected at launch. No zoo of
separate executables and explicitly no reintroduction of slurpd, the
separate replication daemon whose death was one of 2.4's best features. The
router runs as a sub-process under a supervisor that owns lifecycle only: no
data, no routing decisions, no protocol surface. The supervisor is the same
binary in supervisor mode. Supervisor restart does not restart children, or
the isolation win is lost.

Restart of a role is `ldapctl routing restart`, driving the systemd
instantiated unit rather than a private supervisor IPC, so there is one
restart path rather than two that can disagree. Management verbs belong to
`ldapctl`; the server binary does not do management.

---

## 6. Item 30: no caching

No caching mechanisms of any kind.

Reasoning. Payloads are under 100kb per request and response. Storage and
memory are cheap. A ten thousand person institute produces a few binds per
second at the morning peak, under three per second even if every person
signs in within the same hour, which is nothing for a single mdb-class
backend. The read-volume argument that justifies caching belongs to shops
running billions of reads, and those shops do not use LDAP for it anyway.
Designing for their profile is designing for people who are not the users.

Network slowness is not the directory's problem. If a remote is
unreachable, the mechanisms exist to say "that part over yonder is down."
Do not paper over it with stale data.

The pcache use case the book presents, a branch surviving WAN problems, is
answered properly by section 2: the branch holds a real cluster member, a
learner (item 16) for read availability without quorum liability, or its own
consensus group (item 20) if it needs local writes. A real replica with real
consistency, not a stale partial copy with per-template TTLs.

**Negative caching considered and rejected.** It saves a round trip that
costs nothing, and it introduces the provisioning bug directly on the FEIDE
path: an account is created in the upstream, a miss cached thirty seconds
earlier is still live, and the account does not exist until the TTL expires.
The one genuine benefit, absorbing enumeration attacks, is taken as rate
limiting under item 17 admission control instead. Rate limiting does not lie
about what exists.

Implementation note: rate limiting alone does not close enumeration if a
miss returns measurably faster than a hit. Constant-time existence checks
are the other half.

**Item 29: fail closed.** A backend unreachable means the search errors
rather than returning a partial result set. LDAP has no clean wire
representation for "here are 800 entries, one subtree is missing": the
candidates are resultCode 4 with the wrong fixed semantics, LDAPv2's
deprecated partialResults, continuation references (banned with referrals),
or success plus a diagnosticMessage string no client parses. Every
approximation either misleads clients or requires universal client support.
Fail closed is safer, honest, and matches the opinionated-defaults stance.
Revisit in early iteration if operational experience demands it.

---

## 7. Item 34: translucent mode

Local attribute augmentation is a first-class proxy mode: one proxy type
that does what slapo-translucent does, natively, with no caching half. This
is the shape FEIDE needs. Active Directory keeps owning the person, NVI owns
the norEdu* and eduPerson attributes, and nobody has to ask the Windows team
to extend the AD schema. Translucent exists precisely because the upstream
cannot be made to change; "fix your shit" is not available when the shit
belongs to another team.

Dropping the cache half means the mode is purely "local attributes overlaid
on remote entries," not a partial replica. What pcache stored, copies of
remote entries for speed, item 30 already rejected.

**Declared ownership map.** Config states which attributes are local;
everything else is remote. Not inferred from write patterns or first-writer.
Consistent with genesis-asserted-never-inferred. Attributes the remote owns
go remote, attributes only the local side defines go local, and the proxy
decides by attribute, not by a global write-destination setting.

**Scope constraint (the one-to-one rule).** The same map declares which
subtree the local store may be written into. Writes outside the declared
scope are refused regardless of identity. This closes the slapd hole where
the translucent proxy's rootdn can write local entries under DNs it cannot
even read remotely, because the local database has no knowledge of the
remote's ACL decisions and rootdn is exempt from its own.

**No bypass identity.** slapd's rootdn is not "root can override," it is
"root is not checked": it bypasses ACL evaluation entirely, cannot be
constrained by `access to` rules, and `limits` do not apply to it. ldap4 has
no such identity. Administrative privilege is granted, evaluated and logged
like every other privilege. The ownership map's scope constrains every
writer without exception, including the most privileged operator credential.

**Break-glass required, design deferred.** The no-bypass position and the
scope constraint together mean there is no recovery path when the
authorization data itself is broken, and "the ACL store is corrupt and
nobody can fix it" is a real 3am scenario. Break-glass is therefore a
requirement, in tension with no-bypass by construction, and the middle
ground is what needs designing. Azure's model is the reference: dedicated
emergency accounts, excluded from conditional access, credentials split and
stored offline, use triggers alerting, mandatory post-use review.
Break-glass as an audited event, never a standing privilege.

**Collision.** Remote wins. The proxy is never authoritative. If the remote
later grows an attribute that was declared local-owned, ownership has
silently changed hands: log it loudly rather than swallowing it, then update
the local value from remote or drop the local value.

**Deletion.** If the remote dropped the entry, the local overlay row is
dropped too, but via deliberate reconciliation, never via incidental absence
during a request. The proxy cannot see a delete; it sees absence, and
absence has other causes: remote unreachable, proxy account lost read
rights, entry moved OU, scope or filter changed. Deleting on incidental
absence means a transient AD hiccup wipes norEdu* data that exists nowhere
else. The reconciliation pass runs against a verified-healthy remote
connection, confirms absence deliberately, tombstones rather than
hard-deletes, and purges after a retention window.

The hazard that makes this non-optional: DN reuse. If the local row survives
and the remote later recreates the same DN for a different human, the old
attributes reattach to the new person. At a research institute with rotating
staff this will happen.

**Open fork, decide before the FEIDE lab.** Whether local-only attributes
must be filterable. "Excuse me sir, this is an LDAP, not a Wendy's, we do
not carry that" works as a fail-closed position, but FEIDE queries exactly
the attributes that live locally, eduPersonPrincipalName and friends,
because AD does not hold them. Either local attributes are filterable, or
they must not be local. One or the other, before the lab phase.

---

## 8. Item 35: protocol strictness

An unknown protocol element or control fails the operation. Not dropped
silently, not ignored as non-critical. Loud log naming the element. LDAP's
control-criticality distinction, where a non-critical control may be
silently ignored, does not exist: everything is critical, because an
operation half-understood is an operation that should not proceed.

This removes forward compatibility as a wire property, so version
negotiation is the only path and must be explicit. The mechanism is trivial
and sshd is the proof: version exchange in the first line, both sides pick.
What rots in practice is not the version banner but the supported-feature
sets, which is a policy question about the window, not a protocol complexity
problem. Support window declared at compile time per client, server
publishes its own window, intersection computed at connect rather than
assumed.

**Window policy is admin-configurable**, with a project-level statement that
LDAPv3 support sunsets five years after ldap4 release.

Sunset does not mean deletion. It means: "if you want an ldap4 that speaks
ldap3, download this last version; this is your on-ramp to ldap4." The final
v3-speaking build is pinned, archived and named. It carries the highest test
burden in the line, tested to the tits, not the lowest, because it is the
path everyone takes in. Security support terms for that pinned build still
to be decided, even if the answer is security-only for a fixed term then
nothing.

No contradiction with `ldapsearch` surviving permanently (item 8 and the
Part 8 tooling decision): ldapsearch is an alias, a symlink speaking ldap4
under the hood, there for people with chronic muscle memory. Client-tool
compatibility is permanent; wire-protocol v3 compatibility is five years.
The alias is a muscle-memory affordance, not a compatibility surface.

### Extended operations are removed

Carried from Part 7, same reasoning as unknown-control rejection.

LDAP extended operations are opcodes beyond the core nine, identified by OID
and carrying arbitrary payloads: the escape hatch by which the protocol grew
without a version bump. ldap4 needs none of the famous ones. StartTLS is
already crossed out. Password Modify (RFC 3062) dissolves under the
Kerberos-only stance, since the KDC owns credential changes; it is also the
op that crashes slapd under ITS#9538 in the lab, a fitting epitaph. WhoAmI
and cancel become core operations rather than bolt-ons (Part 8: one
acknowledged cancel, no abandon).

The failure of extended operations was not extensibility in principle. It
was extensions arriving as opaque blobs that bypass the semantics of the
core: gates, authorization evaluation and replication. The stated
consequence: adding an operation later requires a protocol version bump,
which the version negotiation above is the honest mechanism for.

### Read-only is a storage-unit state

The slapd `readonly` directive gates the modify opcode, so Password Modify
walks straight through it: a "read-only replica" silently accepts password
changes that then diverge from the provider. The root error is an
operation-level gate protecting a data-level invariant; any second opcode
that mutates data routes around it, and extended operations were an
open-ended supply of second opcodes.

In ldap4, read-only is a state of the storage unit, enforced where writes
land rather than where operations enter. No opcode, present or future, can
route around it. This is what makes the partition self-demotion in section 3
trustworthy rather than aspirational: when a minority node says it is
read-only, nothing gets in through a side door.

---

## 9. Item 33: OIDC and OAuth2

FEIDE already integrates primarily via OIDC and SAML, with the LDAP surface
as what the home organisation exposes for FEIDE to read. A directory that
cannot speak OIDC needs a separate identity provider bolted alongside, which
is the 1980s federation problem restated: one more organ with its own store
and its own trust-by-convention seam.

The hard part is not the token endpoint. An OIDC subject is an opaque
issuer-plus-sub pair and the DIT wants a DN. Something must own that
binding, it must be a real DIT entry under the existing rule that any DN
used for authentication is a validated entry, and it must survive the
issuer rotating subject identifiers.

Decide early whether ldap4 is the relying party consuming tokens or the
issuer. Those are different products. Deferred for deliberate thought, not
for lack of importance: the OIDC/SAML study is on the FEIDE critical path
regardless.

---

## 10. AD compatibility strategy

Partial AD replacement: the LDAP surface only, for now. Domain logon stays
with AD. No Windows client should be able to tell apart the ldap4 LDAP
service and the Windows Server LDAP service.

Full AD replacement is a separate, long-horizon project, explicitly out of
scope for FEIDE and for the current book arc, to be done on ldap4's own
terms rather than by following Samba. Samba should slim down back to serving
files. What that scope honestly contains, for whenever it is picked up:
Windows domain logon is Kerberos plus DCE/RPC plus SMB plus DNS with LDAP as
one leg of a four-legged animal, and Samba's two decades on it are the
honest effort estimate.

What LDAP-surface indistinguishability actually demands:

- AD's schema as shipped, including the MSADat attribute space (already
  parsed into the project's schema tooling)
- AD's DIT layout: `CN=Configuration`, `CN=Schema`, and the rootDSE
  attributes Windows probes on connect
- `objectSid`, `objectGUID` and `sAMAccountName` semantics, not just
  storage: objectSid has structure Windows validates and uses for
  authorization, objectGUID must be stable and unique
- AD's controls: paged results, `LDAP_SERVER_NOTIFICATION_OID`, ranged
  attribute retrieval for large groups
- SASL GSS-SPNEGO, since Windows clients bind that way rather than simple

The rootDSE is the first thing a Windows client reads and the first place a
mismatch is detected. Work starts there.

The split that must be written into any estimate: the schema and rootDSE gap
analysis is mechanical, dump both sides, diff, fill, and the visual diff
tooling covers it. The semantics are implementation, not mapping. Behaviours
and value structures do not come from an alias table.

### Permanent DN aliases

Microsoft has more money to throw at compatibility than this project ever
will. The response is not to crash against that wall like a wave but to be
like water and flow with it.

DN aliases are a coping mechanism for that asymmetry, and therefore
permanent, not migration scaffolding with a sunset. Old DN forms, AD-style
and legacy OpenLDAP-style, resolve to the real tree location indefinitely.
If a DN in ldap4 is an actual tree location rather than just a record label,
pointers from the old locations are what make migration smooth and what make
the service addressable in Microsoft's terms without anyone changing
anything on day one.

**Canonical form is the core intersection** (defined below). AD DNs and
legacy OpenLDAP DNs are served as aliases pointing at it. Logs, audit
records and the change feed all speak canonical, so the audit trail is never
ambiguous about what got touched.

Writes through an alias DN are accepted, resolve to the canonical entry, and
are applied there. The log is very loud about it, like an old man cursing at
a cloud: canonical DN, alias form used, which client used it. Nothing
silent, nothing inferred.

### Product framing: the Venn diagram

Ship understanding both schema sets out of the box: "we do both Windows AD
and OpenLDAP; the Venn intersection is our core; here is a visual
representation of what is not in the core on each side."

This turns the biggest adoption objection, "does it work with my existing
directory," into the thing the project leads with, and that is the goal: to
be able to serve anybody. The tooling already exists: the schema parser and
poster generator produced exactly this artifact for the fifteen OpenLDAP
schemas, and the MSADat parse is already in the project files. Generate the
Venn diagram early, because it doubles as the implementation scoping
document for the compatibility surface.

### Online migration

Target: 15-20 minutes total on reasonable hardware for AD-to-ldap4 and
OpenLDAP-to-ldap4 migration, and back, with reads served throughout.

Approach: all servers are told "migration, go read-only" for the duration
rather than attempting delta catch-up against a moving source. Simpler,
honest, consistent with fail-closed, and enforced by real storage-unit
read-only state (section 8). Reads keep working; writes stop. It is a
maintenance window, a short one, and it should be described as exactly that.

The number, honestly derived: bulk copy is not the bottleneck; ten thousand
entries is seconds of mdb-class writes. The window is set by schema
validation on every entry, index building, and the operator's verification
pass before the switch. Under five minutes of actual read-only for a ten
thousand user directory, with 15-20 minutes as the whole operation including
preparation and verification. Above roughly five hundred thousand entries
the index build dominates and the number must be re-measured, not
extrapolated. State it as a function of directory size, never as a flat
claim.

Caveats: read-only can only be imposed on servers under your control, and in
an AD migration the source may belong to a team that will not freeze it. A
migration that stops on the first schema-invalid entry is a migration nobody
finishes, so entry rejection handling needs an explicit policy given
every-node-validates; the Part 3 migration-tool decision applies, per-record
diffs with unknown attributes flagged for review rather than silently
dropped.

---

## 11. Client surface and operations

**Item 24: native NSS and PAM**, replacing SSSD, with `sshPublicKey`
mandatory but nullable on user entries. SSSD is doing a shitload of lifting
by replicating the translucent proxy badly: it is a translucent proxy plus a
cache plus an NSS/PAM shim, running on every client, configured
independently on every client. All three jobs belong on the server side or
in the protocol. Its configuration difficulty is downstream of that: it has
to be told everything, domains, providers, mappings, enumeration, override
files, because the directory refused to make any of it discoverable.
Compensating tooling is evidence of wrong defaults, and SSSD is the largest
single piece of compensating tooling in the ecosystem.

**Item 25: home directory as a location the directory states**, not a
configuration string it stores. The concrete instance of the section 1
framing: automount strings and split home attributes are the NFS seam.

**Item 9: promote and demote playbooks.** Ansible rehearsal of the v1
promotion command semantics (section 2), queued as chapter-end lab work.

**Item 22 (operational half): decommission-cluster.yml**, the playbook that
ends a cluster node by node, since no destroy verb exists.

**Item 11: liveness as core.** Specified in section 3.

**Item 18: anomaly detection module** in the config DIT: unusual bind
patterns, enumeration attempts, mass reads, surfaced by the server itself
rather than by an external log scraper. Feeds the item 17 admission control.

**Item 12: the pitch.** Still to be written. The Venn diagram framing in
section 10 is probably its spine.

**Item 21: adopt versus merge.** Adopting an existing directory is a
supported, scriptable operation. Merging two live clusters is a GUI wizard
with warnings, because it is a human decision with data-loss consequences.
Section 3's dual-force-marker reconciliation lands here.

---

## 12. Item 14: test strategy

Rust is the implementation language. It removes the memory-corruption class,
use-after-free, buffer overruns, that produced most of OpenLDAP's historical
CVE list. What remains is logic, and exploits in Rust are logic, so the
issues will be logic mistakes. What that means concretely for a directory:

- authorization logic, the ACL engine, pure logic
- parser differentials, where the BER decoder and someone else's disagree
  about the same bytes
- DN and string canonicalisation, normalisation mismatches, Unicode
  confusables
- timing side channels in credential comparison
- resource exhaustion, since Rust allocates happily until the OOM killer
  arrives
- `unsafe` blocks and any linked C library for crypto or storage

Parser differentials and canonicalisation are the two worth worrying about
most, and neither is a memory-safety class.

The response is test-to-the-tits as method: each subsystem lands with its
paranoid test load before the next starts, replication first per the item 8
build order. But hand-written cases run out fast: a thousand cases you
thought of do not find the input you did not. Required test classes:

- property testing (`proptest`/`quickcheck`) for invariants such as
  apply-in-any-order-converges
- fuzzing (`cargo-fuzz`) on the wire decoder
- deterministic seeded simulation of the whole cluster in one process, so a
  consensus failure reproduces exactly: the FoundationDB and TigerBeetle
  method, and the only thing that makes consensus bugs findable at all
- deterministic fault injection for partitions

**Jepsen** (carried from Part 7). Kingsbury's framework: run a small
cluster, throw concurrent operations at it while injecting partitions,
clock skew, process kills and pauses, record every operation, check the
history against the claimed consistency model. Checkers are Knossos and
Elle. It broke almost everything pointed at it, and "passed Jepsen" is the
de facto credibility bar for distributed database claims. When replication
exists, a Jepsen-style proof of convergence and no lost writes on a
five-node cluster is the evidence that matters.

**Partition scenarios as a required test class**: four-four even split,
branch outvotes headquarters, forced override on one side, forced override
on both sides simultaneously, rejoin with resync incomplete. The both-sides
case must be tested explicitly, because the override verb is designed to
make it hard rather than impossible.

**Named test target**: the final v3-speaking build (section 8).

**Scale of evidence, not scale of deployment** (carried from Part 7).
Correctness arguments come from adversarial testing on small clusters.
Performance arguments come from published single-node numbers on documented
hardware. The proof-of-concept is one node with ten million entries plus a
five-node replication cluster with fault injection; all of it fits on 3jane
or a week of rented capacity. A thousand-VM demonstration is theater: real
money, weeks of orchestration plumbing that teaches nothing about ldap4, and
it invites the obvious question from exactly the people whose respect is
wanted, why does a directory need a thousand nodes. No directory serves a
billion entries from one tree; at that point it is sharded, which item 20
covers.

---

## 13. Carried forward from earlier parts

Unchanged, listed for completeness with their origins:

- `require authc` is the default and cannot be turned off
- Kerberos-only authentication as the destination; passwords as a phased-out
  ramp; no passwords in the directory means no Password Modify op and no
  password policy surface
- the directory has no business with password policy of any kind: quality,
  history, change-freshness belong to the credential authority
- argon2id as the one permitted password scheme, if passwords are stored at
  all during the ramp
- management binary is `ldapctl` everywhere, never `ldap4ctl`
- two-binary client surface: `ldapctl` operator, `ldapq` user; `ldapsearch`
  as a permanent alias with flag translation and deprecation warnings
- tenant isolation by process-per-tenant, systemd instantiated units, MCS
  SELinux categories, cgroups: not ACL walls
- opinionated mandatory core with extension points on top,
  Kubernetes-not-Mesos
- log output human-readable at every level, junior-admin-at-3am bar
- log store inherits the primary database ACL; no secrets in logs
- schema-as-DIT as the native discovery form, `cn=subschema` as a generated
  compatibility view; sanctioned versioned core schema collapsing discovery
  to a capability handshake
- collapse the four-layer schema stack (attributetype, objectclass,
  ditcontentrule, structure rules) into one schema language expressing
  composition and placement constraints directly; validity is never encoded
  as authorization, because a validity rule that depends on who is asking is
  not a validity rule
- ACL engine: materialized deny-wins evaluation, precomputed bitmask hot
  path, no config file, live `ldapctl` edits, `acl explain` and `acl lint`
  first-class
- whole-word privilege names, never single letters
- no experimental namespace in production, ever
- anonymous bind off by default; per-application anonymous-bind bridge
  (`ldapctl bridge`) narrows an identity for legacy apps, the opposite blast
  radius of idassert which widens one
- any DN used for authentication is a real DIT entry, schema-validated
- no binary blobs in schema: photo and audio store URLs only;
  userCertificate inline retained as a deprecated temporary exception
- one duration grammar; one acknowledged cancel, no abandon; controls kept
  but paging and sort in core; inline comments in config
- `ldapexport` and `ldapimport` replace `slapcat` and `slapadd`, `--json`
  for jq interoperability, no side-door utilities that bypass the running
  server
- online index builds; no offline slapindex equivalent
- migration tool produces per-record diffs, old schema left, new schema
  right, unknown attributes flagged for review rather than silently dropped
- krbctl owns realm bootstrap (`krbctl realm init` for greenfield); ldap4
  never bundles a KDC and consumes a realm via DNS SRV discovery, explicit
  kdc pointer as override; Rust strangler-fork of MIT krb5 preserving wire
  compatibility and the GSSAPI C ABI is the parked Kerberos plan
- GPL3 single license

---

## 14. On the configuration store question

cn=config was upstream OpenLDAP (2.3), not Debian; Debian and EL followed
the default. What it was after was real: online change without restart,
which for a replicated directory means no write outage to add an overlay or
an index; config replicated by the same syncrepl machinery as data; config
queryable and ACL-controlled with the same tools as everything else; and
config validated against schema at write time rather than at next startup.

The criticism that lands: it kept the file as the substrate and layered a
directory view on top, a half measure instead of a major rewrite. One owner
was never chosen. The result is neither hand-editable nor a real store:
unreadable on disk, undiffable in git, uncommentable, ordering encoded in
`{0}` prefixes, every operation needing a running server.

The conclusion is not a return to a config file, which delivers none of the
four goals. It is one authoritative store, live-editable through `ldapctl`,
with export and import for git, and no pretence that the on-disk form is the
interface. That is already the banked position for the ACL engine, and the
validated-at-write-time property is the one ldap4's schema-as-DIT position
shares with cn=config, which is worth admitting.

---

## 15. Benchmark plan

Build one harness, protocol-agnostic where possible, used against both slapd
and ldap4, because both need slamming. slapd is the baseline number and the
black-box oracle (item 26), so the same harness serves correctness
comparison and load comparison.

Record hardware, dataset and query mix with every run, or the numbers are
not comparable six months later.

Dataset generation: `generate_dit.py`, already written, including the
parser-torture edge cases (UTF-8 base64 values, RFC 4514-escaped RDNs, long
values, binary placeholders, line folding), which double as decoder fuzz
seeds for section 12.

Expected slapd walls, roughly in order: `threads` capping concurrency before
CPU does, unindexed filter attributes turning searches into full scans, mdb
`maxsize` against RSS, TLS handshake cost when every query opens a
connection, `sizelimit` and `timelimit` cutting off before the server does.

**On hardware claims.** A directory workload at these scales is not
CPU-bound and does not need dual-socket EPYC; the 96-core Threadripper
already planned exceeds what slapd will use before hitting thread limits and
lock contention. Storage matters in exactly one place: fsync latency on the
write commit path, since mdb commits with a synchronous flush and every
write op waits on the device round trip. RAID gives bandwidth, which is not
the constraint for random small-page latency-bound reads, and is neutral to
negative for fsync. What moves the write number:

- power-loss protection, which acknowledges flush from DRAM; consumer drives
  honour it to NAND, often an order of magnitude slower
- batching, item 15, one transaction over many entries
- durability mode (`dbnosync`-equivalent), faster and loses the last
  transactions on power loss: a real tradeoff, not a free win
- write amplification from copy-on-write page splits, a page-size and layout
  question

PLP requires capacitors, which do not fit M.2's board area or thermal
budget. Enterprise PCIe 5.0 NVMe with PLP at 7.68TB exists in U.2, U.3 and
E3.S: Solidigm D7-PS1010, Kioxia CM9, Samsung PM1743. Verify current
availability before committing; the segment moves. The Rocket 1608A cards
take M.2, so U.2 means an adapter or an HBA.

Sequence: run the consumer-drive floor benchmark on existing hardware,
publish it honestly, stating the bottleneck actually found rather than the
hardware owned, since a claim of "tested on PCIe 5.0 NVMe RAID" for a
workload that never left page cache is noise someone will call. Then
approach Kioxia for a loan box with U.2 or U.3. A cold ask gets nothing; an
ask backed by a published benchmark and a named project gets answered. Hard
acknowledgement of Kioxia in the writeup; thanking a vendor for hardware is
standard practice, and "I am not made of money, I am just a sysadmin" is a
complete answer to anyone who minds. The one line that matters: the numbers
say what they say, including when the loaned drive loses, and a vendor who
wants a different deal is not worth the loan.

Queued: slapd strain test using `generate_dit.py`, after the Chapter 7
checklist.

---

## 16. Open questions

1. Whether local-only attributes must be filterable under item 34. Decide
   before the FEIDE lab.
2. Break-glass design under item 34: the middle ground between no-bypass and
   a recoverable directory.
3. Security support terms for the pinned final v3-speaking build.
4. How far back the version support window extends as a published promise,
   beyond the v3 five-year statement.
5. Whether ldap4 is relying party or issuer under item 33.
6. Entry-rejection policy during migration, given every-node-validates.
7. Whether any referral-shaped mechanism survives for non-core purposes
   (item 3 note: "can be useful, need to think how").
8. What, if anything, of the site-weight policy layer above raft gets built
   versus solved by voter placement plus sharding.
9. Item 12: the pitch, still unwritten.
