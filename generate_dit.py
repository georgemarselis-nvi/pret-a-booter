#!/usr/bin/env python3
"""
LDAP DIT generator — deterministic, seeded LDIF output for any base domain.

Exercises the standard OpenLDAP schemas:
  core, cosine, inetorgperson, nis (posixAccount/shadowAccount/posixGroup),
  kerberos (krbPrincipalAux), duaconf (DUAConfigProfile),
  misc (inetLocalMailRecipient), openldap.schema (OpenLDAPperson/-ou/-org).

Intended to produce test data for LDAP client/server implementations
(attribute options, base64 transfer encoding, DN escaping, line folding,
multi-valued attributes, binary values, SCRAM-SHA-256 userPassword).

Usage:
  ./generate_dit.py example.com
  ./generate_dit.py                       # random (seeded) domain
  ./generate_dit.py corp.example.org --users 25000 --layout nested --seed v2
  ./generate_dit.py example.com --no-binary --no-special-dns --no-fold

Load order matters: the file emits parents before children, so
`ldapadd -f <domain>.ldif` works directly.
"""

import argparse
import base64
import hashlib
import hmac
import random
import re
import sys
import time
import unicodedata

# Filled in by main() from the domain argument (or a random domain).
DOMAIN = "example.com"
BASE = "dc=example,dc=com"
REALM = "EXAMPLE.COM"
ORG = "Example Industries"

DOM_WORDS_A = ["north", "blue", "iron", "silver", "quantum", "polar",
               "cedar", "granite", "lumen", "vertex", "echo", "atlas"]
DOM_WORDS_B = ["forge", "labs", "works", "systems", "dynamics", "grid",
               "stack", "cloud", "data", "logic", "net", "soft"]
DOM_TLDS = ["com", "net", "org", "io", "dev", "is", "de", "co", "tech"]


def random_domain(rng: "random.Random") -> str:
    return (rng.choice(DOM_WORDS_A) + rng.choice(DOM_WORDS_B) + "." +
            rng.choice(DOM_TLDS))


def set_domain(domain: str):
    global DOMAIN, BASE, REALM, ORG
    DOMAIN = domain.lower().strip(".")
    BASE = ",".join("dc=" + p for p in DOMAIN.split("."))
    REALM = DOMAIN.upper()
    ORG = DOMAIN.split(".")[0].capitalize() + " Industries"

# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------

FIRST = [
    "Anna", "Björn", "Carlos", "Dmitri", "Elena", "François", "Guðrún",
    "Hiroshi", "Ingrid", "Jamal", "Katarzyna", "Lars", "María", "Nikolai",
    "Olga", "Priya", "Quentin", "Rósa", "Søren", "Tatiana", "Umar",
    "Valentina", "Wei", "Xavier", "Yuki", "Zoë", "Ahmed", "Beatriz", "Chidi",
    "Dagmar", "Émile", "Fatima", "Gabriel", "Hana", "Ivan", "Jorge",
    "Kirsten", "Leila", "Mateo", "Nadia", "Oskar", "Paulo", "Radka",
    "Sanjay", "Tomás", "Ulla", "Viktor", "Wanda", "Yasmin", "Zbigniew",
    "Aisha", "Bruno", "Cécile", "Diego", "Esther", "Finn", "Greta", "Hugo",
    "Ines", "Jakob", "Kwame", "Lucia", "Magnus", "Noor", "Olaf", "Petra",
    "Rania", "Stefan", "Thandiwe", "Ursula", "Vera", "Wilhelm", "Ximena",
    "Yosef", "Zainab", "Alva", "Boris", "Carmen", "Dariusz", "Edda",
    "Farid", "Gunnar", "Helga", "Igor", "Jón", "Kristín", "Linnea",
    "Mikhail", "Natsuki", "Ólafur", "Pável", "Ragnhild", "Signý", "Takeshi",
    "Unnur", "Vigdís", "Werner", "Yolanda", "Zora",
]
LAST = [
    "Andersen", "Bianchi", "Chen", "Dubois", "Einarsson", "Fernández",
    "García", "Hansen", "Ivanov", "Jónsdóttir", "Kowalski", "Lindqvist",
    "Müller", "Nakamura", "O\u2019Brien", "Petrov", "Quiroga", "Rodríguez",
    "Schmidt", "Tanaka", "Ueda", "Vasquez", "Wagner", "Xu", "Yamamoto",
    "Zhang", "Almeida", "Bergström", "Cohen", "Da Silva", "Eriksson",
    "Fischer", "Gunnarsdóttir", "Haraldsson", "Ito", "Jensen", "Kim",
    "Larsen", "Moreau", "Nguyen", "Olsen", "Popov", "Ramírez", "Sørensen",
    "Tómasson", "Ulrich", "Virtanen", "Weber", "Yılmaz", "Zieliński",
    "Abramov", "Bakker", "Castillo", "Dvořák", "Eze", "Ferreira",
    "Grigoryan", "Hoffmann", "Ibrahim", "Janković", "Kovács", "Lehtinen",
    "Mendoza", "Novák", "Okafor", "Papadopoulos", "Rossi", "Silva",
    "Takahashi", "Umarov", "Vargas", "Watanabe", "Yoshida", "Żuk",
    "Björnsdóttir", "Costa", "Duarte", "Egilsson", "Friðriksdóttir",
    "Guðmundsson", "Horváth", "Ivarsson", "Johansson", "Kristjánsson",
    "Laxness", "Magnúsdóttir", "Nilsen", "Óskarsson", "Pálsson",
    "Ragnarsson", "Sigurðardóttir", "Þórðarson", "Valdimarsson", "Wojcik",
    "Yun", "Zamora",
]
# (cn, sn, givenName) triples in non-Latin scripts — forces base64 in LDIF
NONLATIN = [
    ("Дмитрий Волков", "Волков", "Дмитрий"),
    ("Екатерина Смирнова", "Смирнова", "Екатерина"),
    ("田中 太郎", "田中", "太郎"),
    ("佐藤 花子", "佐藤", "花子"),
    ("王 伟", "王", "伟"),
    ("李 娜", "李", "娜"),
    ("김 민준", "김", "민준"),
    ("박 서연", "박", "서연"),
    ("Αλέξανδρος Παπαδόπουλος", "Παπαδόπουλος", "Αλέξανδρος"),
    ("محمد الأحمد", "الأحمد", "محمد"),
    ("שרה כהן", "כהן", "שרה"),
    ("Θεοδώρα Νικολάου", "Νικολάου", "Θεοδώρα"),
]
DEPTS = [
    "Engineering", "Product", "Design", "Marketing", "Sales", "Support",
    "Finance", "Legal", "People Operations", "IT Operations", "Security",
    "Data Science", "Research", "Quality Assurance", "DevOps",
    "Infrastructure", "Procurement", "Facilities", "Logistics",
    "Customer Success", "Business Development", "Communications",
    "Analytics", "Compliance", "Training", "Field Services",
    "Manufacturing", "Platform", "Mobile", "Localization",
]
TITLES = [
    "Engineer", "Senior Engineer", "Staff Engineer", "Analyst",
    "Senior Analyst", "Manager", "Senior Manager", "Director",
    "Coordinator", "Specialist", "Lead", "Principal", "Associate",
    "Consultant", "Architect", "Administrator", "Intern", "Officer",
    "Technician", "Strategist",
]
CITIES = [
    "Reykjavík", "Kópavogur", "Hafnarfjörður", "Akureyri", "Garðabær",
    "Mosfellsbær", "Selfoss", "Akranes", "Keflavík", "Egilsstaðir",
]
STREETS = [
    "Laugavegur", "Skólavörðustígur", "Hverfisgata", "Austurstræti",
    "Bankastræti", "Suðurgata", "Hringbraut", "Miklabraut", "Borgartún",
    "Sæbraut", "Grensásvegur", "Fiskislóð",
]
LANGS = ["en", "is", "de", "fr", "es", "ja", "pl", "pt", "ru", "sv", "da", "no"]
SHELLS = ["/bin/bash", "/bin/zsh", "/bin/sh", "/usr/bin/fish", "/bin/false"]
CATEGORIES = ["research", "operations", "commercial", "administration", "technology"]
MAILHOSTS = ["mail01", "mail02"]

HOSTS = [
    ("ldap01", "10.10.1.11"), ("ldap02", "10.10.1.12"),
    ("kdc01", "10.10.1.21"), ("kdc02", "10.10.1.22"),
    ("mail01", "10.10.2.11"), ("mail02", "10.10.2.12"),
    ("web01", "10.10.3.11"), ("web02", "10.10.3.12"),
    ("db01", "10.10.4.11"), ("files01", "10.10.4.21"),
    ("dns01", "10.10.1.31"), ("vpn01", "10.10.5.11"),
    ("build01", "10.10.6.11"), ("monitor01", "10.10.6.21"),
]
STD_SERVICES = [
    ("ldap", "ldap01"), ("ldap", "ldap02"),
    ("kadmin/admin", None), ("kadmin/changepw", None),
    ("HTTP", "web01"), ("HTTP", "web02"),
    ("imap", "mail01"), ("smtp", "mail01"), ("smtp", "mail02"),
    ("dns", "dns01"), ("nfs", "files01"), ("cifs", "files01"),
]
ADD_SERVICES = [
    ("postgres", "db01"), ("git", "build01"), ("jenkins", "build01"),
    ("grafana", "monitor01"), ("prometheus", "monitor01"),
    ("vault", "db01"), ("minio", "files01"), ("redis", "db01"),
    ("elasticsearch", "db01"), ("rabbitmq", "db01"),
    ("docker-registry", "build01"), ("k8s", "web01"),
    ("backup", "files01"), ("openvpn", "vpn01"),
]
CROSS_GROUPS = [
    # (name, membership probability, description)
    ("vpn-users", 0.35, "VPN access"),
    ("developers", 0.30, "Development toolchain access"),
    ("admins", 0.02, "Directory and host administrators"),
    ("oncall", 0.06, "On-call rotation"),
    ("sudoers", 0.04, "sudo on managed hosts"),
    ("backup-operators", 0.02, "Backup infrastructure"),
    ("contractors", 0.08, "External contractors"),
]

LOREM = (
    "The directory information tree exists primarily to "
    "exercise every corner of the LDAP protocol implementation under test, "
    "including attribute options, matching rules, syntaxes, and transfer "
    "encodings. "
)

# minimal valid 1x1 JPEG
TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
    "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAAB"
    "AAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AVN//2Q=="
)

# --------------------------------------------------------------------------
# LDIF writer (RFC 2849)
# --------------------------------------------------------------------------

SAFE_RE = re.compile(r"^[\x01-\x09\x0b\x0c\x0e-\x1f\x21-\x39\x3b\x3d-\x7f]"
                     r"[\x01-\x09\x0b\x0c\x0e-\x7f]*$")


def needs_b64(v: str) -> bool:
    if v == "":
        return False
    return not SAFE_RE.match(v) or v.endswith(" ")


class LdifWriter:
    def __init__(self, fold: bool):
        self.fold = fold
        self.lines = []
        self.entries = 0

    def raw(self, line: str):
        if self.fold and len(line) > 76:
            self.lines.append(line[:76])
            for i in range(76, len(line), 75):
                self.lines.append(" " + line[i:i + 75])
        else:
            self.lines.append(line)

    def comment(self, text: str):
        self.lines.append("# " + text)

    def blank(self):
        self.lines.append("")

    def dn(self, dn: str):
        self.entries += 1
        if needs_b64(dn):
            self.raw("dn:: " + base64.b64encode(dn.encode()).decode())
        else:
            self.raw("dn: " + dn)

    def a(self, name: str, val):
        if val is None or val == "":
            return
        val = str(val)
        if needs_b64(val):
            self.raw(name + ":: " + base64.b64encode(val.encode()).decode())
        else:
            self.raw(name + ": " + val)

    def binary(self, name: str, data: bytes):
        self.raw(name + ":: " + base64.b64encode(data).decode())

    def end(self):
        self.lines.append("")


def dn_escape(v: str) -> str:
    """Escape an RDN attribute value per RFC 4514."""
    s = re.sub(r'([\\,+"<>;=])', r"\\\1", str(v))
    if s and s[0] in "# ":
        s = "\\" + s
    if s.endswith(" "):
        s = s[:-1] + "\\ "
    return s


def to_ascii(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = s.replace("ß", "ss").replace("Ø", "O").replace("ø", "o")
    s = s.replace("Æ", "AE").replace("æ", "ae")
    s = s.replace("Þ", "Th").replace("þ", "th")
    s = s.replace("Ð", "D").replace("ð", "d")
    s = s.replace("Ł", "L").replace("ł", "l")
    return "".join(c for c in s if 0x20 <= ord(c) <= 0x7E)


def slugify(s: str) -> str:
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", to_ascii(s).lower()))


# --------------------------------------------------------------------------
# SCRAM-SHA-256 (RFC 5802 / RFC 7677 key derivation)
# --------------------------------------------------------------------------

def scram_sha256(password: str, salt: bytes, iterations: int) -> str:
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
    b = lambda x: base64.b64encode(x).decode()
    return ("{SCRAM-SHA-256}" + str(iterations) + ":" + b(salt) +
            "$" + b(stored_key) + ":" + b(server_key))


def scram_pool(password: str, rng: random.Random, n: int = 24,
               iterations: int = 4096):
    """A pool of pre-computed hashes (same password, distinct salts) so 10k+
    users don't cost 10k PBKDF2 runs. All entries verify against `password`."""
    return [scram_sha256(password, rng.randbytes(16), iterations)
            for _ in range(n)]


def fake_der(rng: random.Random, length: int) -> bytes:
    """Placeholder DER-ish blob for userCertificate;binary (not a real cert)."""
    return bytes([0x30, 0x82, (length >> 8) & 0xFF, length & 0xFF]) + \
        rng.randbytes(length)


# --------------------------------------------------------------------------
# generator
# --------------------------------------------------------------------------

def generate(cfg) -> LdifWriter:
    rng = random.Random(cfg.seed)
    w = LdifWriter(cfg.fold)
    now_days = int(time.time() // 86400)
    scram = scram_pool(cfg.password, rng)
    admin_dn = f"cn=admin,{BASE}"

    w.comment(f"LDIF for {BASE}")
    w.comment(f'seed="{cfg.seed}" users={cfg.users} depts={cfg.depts} '
              f"layout={cfg.layout}")
    w.comment(f'userPassword: SCRAM-SHA-256 of "{cfg.password}" '
              "(pool of 24 salts, 4096 iterations)")
    w.comment("schemas: core cosine inetorgperson nis kerberos duaconf misc"
              + (" openldap" if cfg.openldap_extras else ""))
    w.blank()

    # ---- suffix + admin -------------------------------------------------
    w.dn(BASE)
    for oc in ["top", "dcObject", "organization"]:
        w.a("objectClass", oc)
    if cfg.openldap_extras:
        w.a("objectClass", "OpenLDAPorg")
    w.a("dc", DOMAIN.split(".")[0])
    w.a("o", ORG)
    w.a("o", DOMAIN)
    w.a("description", f"Test directory for the {DOMAIN} realm")
    w.a("l", "Reykjavík")
    w.a("postalCode", "101")
    w.a("telephoneNumber", "+354 555 0100")
    w.a("facsimileTelephoneNumber", "+354 555 0101")
    if cfg.openldap_extras:
        w.a("displayName", ORG)
        w.a("labeledURI", "https://" + DOMAIN)
    w.end()

    w.dn(admin_dn)
    for oc in ["top", "organizationalRole", "simpleSecurityObject"]:
        w.a("objectClass", oc)
    w.a("cn", "admin")
    w.a("description", "Directory manager")
    w.a("userPassword", scram[0])
    w.end()

    for ou in ["people", "departments", "groups", "roles", "services",
               "hosts", "profiles"]:
        if ou == "people" and cfg.layout != "flat":
            continue
        w.dn(f"ou={ou},{BASE}")
        w.a("objectClass", "top")
        w.a("objectClass", "organizationalUnit")
        if cfg.openldap_extras:
            w.a("objectClass", "OpenLDAPou")
        w.a("ou", ou)
        w.a("description", "Container: " + ou)
        w.end()

    # ---- departments ----------------------------------------------------
    depts = []
    for i in range(cfg.depts):
        name = DEPTS[i] if i < len(DEPTS) else f"Division {i + 1}"
        depts.append({"name": name, "gid": 5000 + i, "members": [],
                      "member_uids": [], "head": None, "secretary": None})
    if cfg.special_dns:
        depts.append({"name": "Sales, EMEA (Über+Test)",
                      "gid": 5000 + len(depts), "members": [],
                      "member_uids": [], "head": None, "secretary": None})

    for d in depts:
        d["dn"] = f"ou={dn_escape(d['name'])},ou=departments,{BASE}"
        w.dn(d["dn"])
        w.a("objectClass", "top")
        w.a("objectClass", "organizationalUnit")
        if cfg.openldap_extras:
            w.a("objectClass", "OpenLDAPou")
        w.a("ou", d["name"])
        w.a("description", d["name"] + " department")
        w.a("businessCategory", rng.choice(CATEGORIES))
        w.a("telephoneNumber", "+354 555 0%d" % (100 + d["gid"] % 900))
        w.a("l", rng.choice(CITIES))
        w.a("st", "Höfuðborgarsvæðið")
        w.a("street", f"{rng.choice(STREETS)} {rng.randint(1, 120)}")
        w.a("postalCode", str(rng.randint(101, 902)))
        w.a("postOfficeBox", f"PO {rng.randint(1000, 9999)}")
        w.a("physicalDeliveryOfficeName", "Building " + rng.choice("ABC"))
        if cfg.openldap_extras:
            w.a("displayName", DOMAIN + " / " + d["name"])
        w.end()
        if cfg.layout == "nested":
            w.dn(f"ou=people,{d['dn']}")
            w.a("objectClass", "top")
            w.a("objectClass", "organizationalUnit")
            w.a("ou", "people")
            w.end()

    # ---- users -----------------------------------------------------------
    uid_seen = {}
    cross = [{"name": n, "p": p, "desc": desc, "gid": 4000 + i,
              "members": [], "member_uids": []}
             for i, (n, p, desc) in enumerate(CROSS_GROUPS)]

    for i in range(cfg.users):
        d = depts[i % len(depts)]
        gn, sn, cn_native = rng.choice(FIRST), rng.choice(LAST), None
        if cfg.utf8 and rng.random() < 0.08:
            cn_native, sn, gn = rng.choice(NONLATIN)
        base_uid = ((to_ascii(gn)[:1] or "x")
                    + re.sub(r"[^a-z]", "", to_ascii(sn).lower())).lower()
        if len(base_uid) < 2:
            base_uid = f"user{i}"
        uid_seen[base_uid] = uid_seen.get(base_uid, 0) + 1
        uid = base_uid if uid_seen[base_uid] == 1 else \
            f"{base_uid}{uid_seen[base_uid]}"
        cn = f"{gn} {sn}"
        dn = (f"uid={uid},ou=people,{BASE}" if cfg.layout == "flat"
              else f"uid={uid},ou=people,{d['dn']}")

        w.dn(dn)
        for oc in ["top", "person", "organizationalPerson", "inetOrgPerson",
                   "posixAccount", "shadowAccount", "krbPrincipalAux"]:
            w.a("objectClass", oc)
        if cfg.openldap_extras:
            w.a("objectClass", "OpenLDAPperson")
            w.a("objectClass", "inetLocalMailRecipient")
        w.a("uid", uid)
        w.a("cn", cn)
        if cn_native:
            w.a("cn", cn_native)
        w.a("sn", sn)
        w.a("givenName", gn)
        w.a("displayName", cn_native or cn)
        w.a("initials", (to_ascii(gn)[:1] or "X").upper() + "." +
            (to_ascii(sn)[:1] or "X").upper() + ".")
        w.a("mail", f"{uid}@{DOMAIN}")
        if cfg.multivalued:
            alias = (re.sub(r"[^a-z]", "", to_ascii(gn).lower()) + "." +
                     re.sub(r"[^a-z]", "", to_ascii(sn).lower()))
            w.a("mail", f"{alias}@{DOMAIN}")
            if rng.random() < 0.3:
                w.a("mail", f"{uid}@corp.{DOMAIN}")
        if cfg.openldap_extras:
            mh = rng.choice(MAILHOSTS)
            w.a("mailLocalAddress", f"{uid}@{DOMAIN}")
            w.a("mailRoutingAddress", f"{uid}@{mh}.{DOMAIN}")
            w.a("mailHost", f"{mh}.{DOMAIN}")
        w.a("employeeNumber", str(100000 + i))
        w.a("employeeType", "permanent" if rng.random() < 0.9 else
            rng.choice(["contractor", "intern", "temporary"]))
        w.a("title", rng.choice(TITLES))
        w.a("departmentNumber", str(d["gid"]))
        w.a("ou", d["name"])
        w.a("o", ORG)
        w.a("telephoneNumber", f"+354 5{rng.randint(100000, 999999)}")
        if cfg.multivalued and rng.random() < 0.4:
            w.a("telephoneNumber", f"+354 5{rng.randint(100000, 999999)}")
        w.a("mobile", f"+354 6{rng.randint(100000, 999999)}")
        if rng.random() < 0.3:
            w.a("homePhone", f"+354 4{rng.randint(100000, 999999)}")
        if rng.random() < 0.1:
            w.a("pager", f"+354 9{rng.randint(100000, 999999)}")
        if rng.random() < 0.15:
            w.a("facsimileTelephoneNumber", f"+354 555 0{rng.randint(100, 999)}")
        w.a("roomNumber", f"{rng.choice('ABC')}-{rng.randint(100, 499)}")
        w.a("l", rng.choice(CITIES))
        w.a("st", "Höfuðborgarsvæðið")
        w.a("street", f"{rng.choice(STREETS)} {rng.randint(1, 120)}")
        w.a("postalCode", str(rng.randint(101, 902)))
        w.a("postalAddress", f"{cn}${rng.choice(STREETS)} "
            f"{rng.randint(1, 120)}${rng.choice(CITIES)}$Iceland")
        if rng.random() < 0.2:
            w.a("homePostalAddress", f"{rng.choice(STREETS)} "
                f"{rng.randint(1, 120)}${rng.choice(CITIES)}$Iceland")
        if rng.random() < 0.1:
            w.a("registeredAddress", f"PO {rng.randint(1000, 9999)}$"
                f"{rng.choice(CITIES)}$Iceland")
        w.a("physicalDeliveryOfficeName", "Building " + rng.choice("ABC"))
        w.a("preferredLanguage", rng.choice(LANGS))
        w.a("labeledURI", f"https://intranet.{DOMAIN}/~{uid} Intranet page")
        if rng.random() < 0.25:
            w.a("carLicense", rng.choice(["AB", "GK", "MX", "RE", "TF"]) +
                "-" + rng.choice("ABDE") + str(rng.randint(10, 99)))
        w.a("businessCategory", rng.choice(CATEGORIES))
        if rng.random() < 0.2:
            w.a("seeAlso", d["dn"])
        w.a("description", longtext(rng) if cfg.long_values and
            rng.random() < 0.05 else "Member of " + d["name"])
        if cfg.binary:
            if rng.random() < 0.12:
                w.binary("jpegPhoto", TINY_JPEG)
            if rng.random() < 0.06:
                w.binary("userCertificate;binary",
                         fake_der(rng, rng.randint(96, 256)))
        # posixAccount + shadowAccount
        w.a("uidNumber", str(10000 + i))
        w.a("gidNumber", str(d["gid"]))
        w.a("homeDirectory", "/home/" + uid)
        w.a("loginShell", rng.choice(SHELLS))
        w.a("gecos", f"{to_ascii(cn)},{to_ascii(d['name'])},,")
        w.a("shadowLastChange", str(now_days - rng.randint(0, 365)))
        w.a("shadowMin", "0")
        w.a("shadowMax", "99999")
        w.a("shadowWarning", "7")
        w.a("shadowInactive", "30")
        w.a("shadowExpire", "-1")
        w.a("shadowFlag", "0")
        # kerberos
        w.a("krbPrincipalName", f"{uid}@{REALM}")
        w.a("krbCanonicalName", f"{uid}@{REALM}")
        # manager / secretary
        if d["head"] and d["head"]["dn"] != dn:
            w.a("manager", d["head"]["dn"])
        else:
            w.a("manager", admin_dn)
        if d["secretary"] and d["secretary"]["dn"] != dn:
            w.a("secretary", d["secretary"]["dn"])
        w.a("userPassword", scram[1 + (i % (len(scram) - 1))])
        w.end()

        user = {"dn": dn, "uid": uid}
        if not d["head"]:
            d["head"] = user
        elif not d["secretary"]:
            d["secretary"] = user
        d["members"].append(dn)
        d["member_uids"].append(uid)
        for g in cross:
            if rng.random() < g["p"]:
                g["members"].append(dn)
                g["member_uids"].append(uid)

    # ---- groups ----------------------------------------------------------
    def emit_gon(name, desc, members):
        w.dn(f"cn={dn_escape(name)},ou=groups,{BASE}")
        w.a("objectClass", "top")
        w.a("objectClass", "groupOfNames")
        w.a("cn", name)
        w.a("description", desc)
        w.a("owner", admin_dn)
        for m in (members or [admin_dn]):
            w.a("member", m)
        w.end()

    def emit_posix(name, gid, desc, member_uids):
        w.dn(f"cn={dn_escape(name)},ou=groups,{BASE}")
        w.a("objectClass", "top")
        w.a("objectClass", "posixGroup")
        w.a("cn", name)
        w.a("gidNumber", str(gid))
        w.a("description", desc)
        for m in member_uids:
            w.a("memberUid", m)
        w.end()

    dept_group_dns = []
    for d in depts:
        slug = slugify(d["name"])
        if cfg.dept_groups:
            emit_gon(slug, d["name"] + " membership", d["members"])
            dept_group_dns.append(f"cn={slug},ou=groups,{BASE}")
        if cfg.posix_groups:
            emit_posix(slug + "-posix", d["gid"], d["name"] + " POSIX group",
                       d["member_uids"])
    if cfg.cross_groups:
        for g in cross:
            emit_gon(g["name"], g["desc"], g["members"])
            emit_posix(g["name"] + "-posix", g["gid"], g["desc"],
                       g["member_uids"])
        if dept_group_dns:
            emit_gon("all-staff", "Nested group of all department groups",
                     dept_group_dns)

    # ---- roles -----------------------------------------------------------
    if cfg.roles:
        for d in depts:
            slug = slugify(d["name"])
            w.dn(f"cn=head-of-{slug},ou=roles,{BASE}")
            w.a("objectClass", "top")
            w.a("objectClass", "organizationalRole")
            w.a("cn", "head-of-" + slug)
            w.a("roleOccupant", d["head"]["dn"] if d["head"] else admin_dn)
            w.a("ou", d["name"])
            w.a("description", "Head of " + d["name"])
            w.a("seeAlso", d["dn"])
            w.a("telephoneNumber", "+354 555 0%d" % (100 + d["gid"] % 900))
            w.end()
        head0 = depts[0]["head"]["dn"] if depts[0]["head"] else admin_dn
        see = f"cn=head-of-{slugify(depts[0]['name'])},ou=roles,{BASE}"
        for name, desc in [("cto", "Chief Technology Officer"),
                           ("ciso", "Chief Information Security Officer"),
                           ("postmaster", "Mail administration"),
                           ("abuse", "Abuse contact"),
                           ("hostmaster", "DNS administration")]:
            w.dn(f"cn={name},ou=roles,{BASE}")
            w.a("objectClass", "top")
            w.a("objectClass", "organizationalRole")
            w.a("cn", name)
            w.a("description", desc)
            w.a("roleOccupant", head0)
            w.a("seeAlso", see)
            w.end()

    # ---- hosts + services --------------------------------------------------
    if cfg.services_standard or cfg.services_additional:
        for h, ip in HOSTS:
            fqdn = h + "." + DOMAIN
            w.dn(f"cn={h},ou=hosts,{BASE}")
            for oc in ["top", "device", "ipHost", "krbPrincipalAux"]:
                w.a("objectClass", oc)
            w.a("cn", h)
            w.a("cn", fqdn)
            w.a("ipHostNumber", ip)
            w.a("krbPrincipalName", f"host/{fqdn}@{REALM}")
            w.a("description", "Managed host " + fqdn)
            w.a("serialNumber", f"SN-{rng.randint(100000, 999999)}")
            w.a("owner", admin_dn)
            w.a("l", "Reykjavík DC1")
            w.end()

    svc_list = ((STD_SERVICES if cfg.services_standard else []) +
                (ADD_SERVICES if cfg.services_additional else []))
    for n, (svc, host) in enumerate(svc_list):
        principal = (f"{svc}/{host}.{DOMAIN}@{REALM}" if host
                     else f"{svc}@{REALM}")
        uid = "svc-" + re.sub(r"[^a-z0-9]+", "-", svc.lower()) + \
            (f"-{host}" if host else "")
        w.dn(f"uid={uid},ou=services,{BASE}")
        for oc in ["top", "account", "simpleSecurityObject",
                   "krbPrincipalAux"]:
            w.a("objectClass", oc)
        w.a("uid", uid)
        if host:
            w.a("host", host + "." + DOMAIN)
        w.a("krbPrincipalName", principal)
        w.a("krbCanonicalName", principal)
        w.a("description", "Service principal " + principal)
        w.a("userPassword", scram[(n + 2) % len(scram)])
        w.end()

    # ---- DUAConfigProfile --------------------------------------------------
    if cfg.dua_profile:
        w.dn(f"cn=default,ou=profiles,{BASE}")
        w.a("objectClass", "top")
        w.a("objectClass", "DUAConfigProfile")
        w.a("cn", "default")
        w.a("defaultServerList", f"ldap01.{DOMAIN} ldap02.{DOMAIN}")
        w.a("preferredServerList", f"ldap01.{DOMAIN}")
        w.a("defaultSearchBase", BASE)
        w.a("defaultSearchScope", "sub")
        w.a("authenticationMethod", "sasl/GSSAPI")
        w.a("credentialLevel", "proxy")
        w.a("searchTimeLimit", "30")
        w.a("bindTimeLimit", "10")
        w.a("followReferrals", "TRUE")
        w.a("dereferenceAliases", "TRUE")
        w.a("profileTTL", "43200")
        w.a("serviceSearchDescriptor", "passwd:" +
            ("ou=people," if cfg.layout == "flat" else "ou=departments,") +
            BASE + "?sub")
        w.a("serviceSearchDescriptor", f"group:ou=groups,{BASE}?one")
        w.a("attributeMap", "passwd:gecos=displayName")
        w.a("objectclassMap", "passwd:posixAccount=posixAccount")
        w.a("serviceAuthenticationMethod", "pam_ldap:sasl/GSSAPI")
        w.a("serviceCredentialLevel", "pam_ldap:proxy")
        w.end()

    # ---- special-DN edge entries --------------------------------------------
    if cfg.special_dns:
        for name, desc in [
            ("Doe, John", "Comma in RDN"),
            ("a+b=c", "Plus and equals in RDN"),
            ("#leading-hash", "Leading hash in RDN"),
            ("trailing-space ", "Trailing space in RDN"),
            ('quote"and\\backslash', "Quote and backslash in RDN"),
            ("semi;colon<gt>", "Semicolon and angle brackets in RDN"),
        ]:
            w.dn(f"cn={dn_escape(name)},ou=roles,{BASE}")
            w.a("objectClass", "top")
            w.a("objectClass", "organizationalRole")
            w.a("cn", name)
            w.a("description", "DN escaping test: " + desc)
            w.end()

    return w


def longtext(rng: random.Random) -> str:
    return (LOREM * rng.randint(12, 24)).strip()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description="Generate a deterministic test LDIF for a base domain",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    B = argparse.BooleanOptionalAction

    p.add_argument("domain", nargs="?", default=None,
                   help="base domain, e.g. example.com "
                        "(random, seed-derived, if omitted)")
    p.add_argument("-o", "--output", default=None,
                   help="output file ('-' for stdout; "
                        "default: <domain-label>.ldif)")
    p.add_argument("--seed", default="ldap4", help="RNG seed")
    p.add_argument("--users", type=int, default=10000, help="number of users")
    p.add_argument("--depts", type=int, default=12,
                   help="number of departments")
    p.add_argument("--layout", choices=["flat", "nested"], default="flat",
                   help="flat: uid=x,ou=people | nested: "
                        "uid=x,ou=people,ou=<dept>,ou=departments")
    p.add_argument("--password", default="Passw0rd!",
                   help="cleartext behind every SCRAM-SHA-256 hash")

    g = p.add_argument_group("groups")
    g.add_argument("--dept-groups", action=B, default=True,
                   help="groupOfNames per department")
    g.add_argument("--posix-groups", action=B, default=True,
                   help="posixGroup per department")
    g.add_argument("--cross-groups", action=B, default=True,
                   help="cross-cutting groups (vpn, admins, developers…) "
                        "+ nested all-staff")
    g.add_argument("--roles", action=B, default=True,
                   help="organizationalRole entries (dept heads + global)")

    s = p.add_argument_group("services (kerberos principals)")
    s.add_argument("--services-standard", action=B, default=True,
                   help="host/ldap/HTTP/imap/smtp/dns/nfs/cifs/kadmin")
    s.add_argument("--services-additional", action=B, default=True,
                   help="postgres/git/grafana/vault/redis/k8s/…")

    x = p.add_argument_group("schema extras")
    x.add_argument("--openldap-extras", action=B, default=True,
                   help="OpenLDAPperson/-ou/-org + inetLocalMailRecipient")
    x.add_argument("--dua-profile", action=B, default=True,
                   help="DUAConfigProfile entry (duaconf.schema)")

    e = p.add_argument_group("edge cases (parser torture)")
    e.add_argument("--utf8", action=B, default=True,
                   help="non-Latin names -> base64-encoded LDIF values")
    e.add_argument("--long-values", action=B, default=True,
                   help="very long description values on ~5%% of users")
    e.add_argument("--multivalued", action=B, default=True,
                   help="extra mail/telephoneNumber values")
    e.add_argument("--binary", action=B, default=True,
                   help="jpegPhoto + userCertificate;binary placeholders")
    e.add_argument("--special-dns", action=B, default=True,
                   help="entries with RFC 4514-escaped RDNs "
                        "(commas, +, quotes…)")
    e.add_argument("--fold", action=B, default=True,
                   help="RFC 2849 line folding at 76 chars")

    cfg = p.parse_args()
    set_domain(cfg.domain or random_domain(random.Random(cfg.seed + "-domain")))
    if cfg.output is None:
        cfg.output = DOMAIN.split(".")[0] + ".ldif"
    t0 = time.time()
    w = generate(cfg)
    out = "\n".join(w.lines) + "\n"

    if cfg.output == "-":
        sys.stdout.write(out)
    else:
        with open(cfg.output, "w", encoding="utf-8") as f:
            f.write(out)

    print(f"wrote {cfg.output}: {w.entries} entries, {len(w.lines)} lines, "
          f"{len(out) / 1e6:.1f} MB in {time.time() - t0:.1f}s",
          file=sys.stderr)


if __name__ == "__main__":
    main()
