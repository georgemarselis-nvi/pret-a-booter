# Chapter 6 parking lot: batch of record

Accumulated across Parts 4 through 9 of the Mastering OpenLDAP Chapter 6
read (LDAP Schemas, book pages 219-347). Thirty-six items plus the
design-notes pile. Sorted by destination, not by discovery order.
Items marked [ldap3] target current LDAP and are actionable now; all
others are ldap4 design inputs.

## A. Protocol and data model (ldap4 design inputs)

1. rootDSE replacement as a named protocol response: server
   self-description is a first-class message, not a magic empty-base
   search.
2. Schema-as-DIT with structured errors: schema elements live in the
   tree, diagnostics reference them precisely.
3. Sanctioned core + versioned extensions + cache handshake: one
   blessed schema core, extensions versioned, clients negotiate what
   they cache.
4. Collapse the four-layer stack (syntax / matching rule / attribute /
   objectclass) where layers add ceremony without meaning.
5. Kill NO-USER-MODIFICATION as a caste; collapse USAGE. Modifiability
   is ACL, not metadata caste.
6. No hidden-by-default attribute classes: operational attributes
   return under normal selection rules, no `+` incantation. Visibility
   is governed by ACL. (Sharpened Part 9; subsumes the discovery half
   of item 5.)
7. Literal attribute selection: what you request is what you get,
   hierarchy expansion is explicit.
8. Attribute hierarchies affect search semantics (parent matches
   children in both filter and selection): keep, but document as core
   semantics, never folklore. (Standing correction from Part 9.)
9. Canonical DN discipline: immutable opaque RDNs; display text is an
   attribute, never a naming component. Commas and dots are for
   humans; naming components must not need escaping.
10. Top single spelling: one canonical form, no case aliases.
11. Lifecycle/OBSOLETE semantics: deprecation is a real state with
    enforcement, not a comment.
12. SYNTAX length enforcement: declared lengths mean something or are
    removed.
13. Collective attributes: rejected. Subtree-inherited values are
    action at a distance.
14. Deny java/corba schemas: the graveyard is not portable.
15. Filter-Undefined diagnostics: an undefined attribute in a filter
    is an error with a name, not silent empty results.
16. Inline comments in config: full comment grammar, not line-only.
    (Trailing-# bug, Part 9 live fix.)
17. One duration grammar: 7d / ISO8601; sunset the 7+00:00 form.
18. One acknowledged cancel; no abandon.
19. Controls kept but paging/sort in core.
20. No experimental namespace in production, ever (the 666 story).

## B. Security, policy, logging (ldap4 design inputs)

21. Policy enforcement core; ALL password policy moves to the
    credential authority. Quality, history, safe-modify: the directory
    has no business with password policy.
22. Credential-state enforcement is server-side and mandatory: the
    server refuses service until the required action occurs. Advisory
    response controls clients may ignore are not a policy mechanism.
    Reference case: ppolicy pwdReset enforced only for clients that
    volunteer `-e ppolicy`. (Item 34 as parked.)
23. Commands are verbs, evidence is append-only: admin unlock and
    force-reset are auditable operations, never raw writes to the same
    attributes that store security history. (From the Part 9
    operational-attributes discussion.)
24. One password scheme: argon2id, if passwords exist at all.
25. Logging as core; log store inherits primary ACL; no secrets in
    logs.
26. Audit format core with mandatory actor/outcome/timestamps.
27. ldapq replay from audit records.
28. Log output human-readable at every level.
29. Monitor/introspection entries carry real identity in the answer:
    overlay names, not ordinal slots (cn=Overlay 2 is
    anti-information). (Part 9 parking rule.)
30. Shipped schemas carry their own inventory documentation, queryable
    from the server, not folklore. Corollary of A.2: if schemas live
    in the DIT, the inventory is a search away. (Item 32.)
31. SSH public key support ships in the sanctioned core schema, not as
    a third-party bolt-on. (Part 9, after openssh-lpk.)

## C. Tooling (ldap4 design inputs)

32. Tooling as bait and finish: kubectl/openstack orthogonality.
33. Two-binary client surface: ldapctl (operator) + ldapq (user);
    ldapsearch permanent alias with flag translation and warnings; no
    sunset for tooling compat.
34. ldapq bare invocation: discover connection from config/environment,
    authenticate by default, prompt interactively for what to search.
    Flags are for scripts, not humans. (Part 9.)
35. Self-targeted credential operations never ask for the same secret
    twice: tooling detects self-change and fills bind and payload from
    one prompt. (Item 33 as parked.)
36. Rust strangler-fork of MIT krb5: wire-compatible, GSSAPI C ABI
    kept.
37. Hotel California easter eggs: allusion not quotation, devel builds
    only.

## D. Actionable now [ldap3]

38. Publish an opinionated OID-arc and schema-authoring standard:
    branch-numbering convention, copy-paste definitions for the common
    cases (string attribute, integer attribute, auxiliary decorator,
    structural with SUP), explicit anti-wheel-reinvention stance.
    Standalone publication, reputation asset; ldap4 later inherits it
    as the sanctioned core convention, pre-validated by field use.
    (Item 36 as parked; also in memory.)
39. OID-to-name compat table (tooling for the explorer and cheatsheet).
40. Explorer grouped-view toggle.
41. System-schema gap in posters (operational schema absent from the
    poster set).
42. Names-primary + arc tooling.
43. Schema authoring format with RFC 4512 as compile target.
44. DNS zone editor survey.
45. Prune pilot graveyard + transition shim.
46. Capability = schema + code as one unit (overlay lesson: ppolicy
    module carries its own schema on Debian 2.5+; the file-include era
    is over and the docs never said so).

## Bug of record

accesslog + ppolicy passmod crash: RFC 3062 Password Modify under
`logops all` aborts slapd via assert(0) in accesslog_response
(accesslog.c ~1623, verified 2.6.10+dfsg-1, unfixed on
OPENLDAP_REL_ENG_2_6 as of 2026-07-25). Full mechanism and fix in the
cheatsheet. Candidate upstream ITS report: minimal reproducer exists.

## Standing corrections carried forward

- ppolicy draft never became an RFC (expired, like accesslog schema
  and authPassword). Relax Rules likewise: draft-zeilenga-ldap-relax,
  shipped enabled since 2.4 regardless.
- auditBind/auditSearch/auditObject observed live in cn=log.
- Attribute-specific ACL rules shadow general ones completely: any
  identity needing access to a guarded attribute must appear in that
  attribute's own rule. (err=53 case, fixed live with by self =xw.)
