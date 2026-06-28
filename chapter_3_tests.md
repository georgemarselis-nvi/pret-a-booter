# Chapter 3 Tests - OpenLDAP slapd 2.6.x

## Results

- [x] **TODO 1: grouped multi-attr add** - `add: description title` on one line (page 122)
  - FAILS on slapd 2.6.x with `wrong attributeType at line 4`
  - LDIF: `grouped-add-fail-test.ldif`

- [x] **TODO 2: dash-separated multi-attr add** (page 124)
  - WORKS on slapd 2.6.x
  - LDIF: `grouped-add-test.ldif`

- [x] **TODO 3: delete ALL values of an attribute** (page 123)
  - `delete: title` with no value removes ALL values silently
  - barbara had two title values; both removed
  - LDIF: `del-all-title.ldif`

- [ ] **TODO 4: delete ONE specific attribute value** (page 123)
  - `delete: title` + `title: Senior Researcher` removes only the named value

- [ ] **TODO 5: modrdn rename** (page 125)
  - rename `uid=barbara` to `uid=bjensen`, `deleteoldrdn: 0`
  - verify both `uid=barbara` and `uid=bjensen` present on entry

- [ ] **TODO 6: modrdn restore** (page 125)
  - rename back `uid=bjensen` to `uid=barbara`, `deleteoldrdn: 1`
  - verify old value `uid=bjensen` gone

- [ ] **TODO 7: newsuperior** (page 126)
  - move `uid=barbara` to a different OU
  - verify `ou` attribute behavior on slapd 2.6.x vs book claim (page 126: book says ou=Users retained; margin note says false with deleteoldrdn: 1)

- [ ] **TODO 8: ldapmodrdn vs ldapmodify modrdn** (page 129)
  - confirm they produce identical results

- [ ] **TODO 9: ldapdelete** (page 128)
  - delete a test entry, verify gone

- [ ] **TODO 10: restore DIT**
  - add all test entries back via `ldapadd` after cleanup
