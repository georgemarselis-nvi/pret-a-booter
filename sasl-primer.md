# SASL Primer

For use with OpenLDAP slapd.conf

Copyright (C) 2026 George Marselis

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.


This file tries to explain the basics of SASL without you needed to be a Dunkirk survivor.

## What is SASL?

SASL  ([Simple Authentication and Security Layer, RFC 4422](https://www.rfc-
editor.org/rfc/rfc4422)) is a framework that lets protocols outsource
authentication instead of inventing their own. Rather than LDAP, SMTP, IMAP
and every other protocol each rolling their own broken login system, SASL
provides a plug-in interface: the protocol says "we need to authenticate"
and SASL handles the how.

The "Simple" in the name is aspirational. SASL itself is simple; the
mechanisms it hosts range from "*fine*" (SCRAM) to "*what were they thinking*"
(DIGEST-MD5) to "*For the love of everything sacred, no*" (NTLM).

The way it works: the server publishes a list of mechanisms it accepts.
The client picks one. They do the exchange that mechanism requires.
Done, you are authenticated. The protocol continues. SASL gets out of
the way.

The catch: SASL is only as good as the mechanism you pick. Picking
DIGEST-MD5 because it was the mandatory LDAPv3 mechanism in 2000 means
storing cleartext passwords in a separate database nobody syncs.
Picking SCRAM-SHA-256 means doing it correctly. Picking GSSAPI means
not storing passwords in LDAP at all, which is the correct-most answer.

SASL does not encrypt the connection by default. TLS, in practice, handles the
security layer after authentication, but some mechanisms, such as DIGEST-MD5,
make use of a secondary password database, which is completely separate from the
system one. SASL negotiates who you are. Everything else is the problem of TLS.
See below in "How DIGEST-MD5 Works (and Why It Is Broken)".

## All SASL Mechanisms

| Mechanism     | RFC        | Status          | Notes                                                                                                                  |
|---------------|------------|-----------------|------------------------------------------------------------------------------------------------------------------------|
| PLAIN         | RFC 4616   | Usable          | Cleartext password; relies entirely on TLS for security; never use without TLS 1.3                                     |
| LOGIN         | -          | Obsolete        | Alias for PLAIN with no additional security; superseded                                                                |
| DIGEST-MD5    | RFC 6331   | Broken          | Cryptographically broken; deprecated 2011; do not deploy                                                               |
| CRAM-MD5      | RFC 2195   | Weak            | No mutual authentication; vulnerable to offline dictionary attacks                                                     |
| SCRAM-SHA-1   | RFC 5802   | Acceptable      | Minimum acceptable SCRAM; prefer SHA-256 or SHA-512 if available                                                       |
| SCRAM-SHA-256 | RFC 7677   | Current         | Current standard; use this as minimum for password-based auth                                                          |
| SCRAM-SHA-512 | -          | Strongest SCRAM | OpenLDAP extension; not in RFC; strongest SCRAM available                                                              |
| GSSAPI        | RFC 4752   | Preferred       | Kerberos 5; correct long-term solution; no passwords in the directory                                                  |
| EXTERNAL      | RFC 4422   | Strong          | Uses TLS client cert as identity; no password; requires PKI                                                            |
| OTP           | RFC 2444   | Undeployed      | S/KEY based one-time passwords; practically nobody uses this; TOTP is not the same thing                               |
| NTLM          | -          | Avoid           | Microsoft proprietary; pass-the-hash vulnerable; relay attack vulnerable; deprecated by Microsoft in favor of Kerberos |

## How Mechanism Lists Work

`slapd` does not use all listed mechanisms simultaneously. It publishes a list
of accepted mechanisms, like a currency exchange listing accepted currencies.
The client picks one mechanism from the list, the strongest it supports, and
the authentication proceeds using only that mechanism.

Listing multiple mechanisms means: "I will accept any of these". It does not
mean they all are used together in sequence and all together must pass to
authenticate.

## How PLAIN Works

PLAIN sends the username and password in cleartext in a single step. There is
no challenge, no response, no hashing. The password is transmitted as-is.

This is not as catastrophic as it sounds, provided TLS 1.3 is enforced at the
transport layer before the bind is attempted. The password is cleartext at the
SASL layer but encrypted by TLS on the wire. Without TLS, PLAIN is trivially
interceptable.

PLAIN does not require a secondary password database. It verifies against
LDAP's `userPassword` attribute directly.

Never advertise PLAIN without `security simple_bind=256` in `slapd.conf`.

## How SCRAM-SHA-* Works

SCRAM (Salted Challenge Response Authentication Mechanism, RFC 5802) is a
mutual challenge-response authentication protocol. The password is never sent
over the wire in any form.

### The exchange

1. Client sends username to server.
2. Server looks up the SCRAM verifier for that user in the `userPassword`
   attribute in LDAP and sends back a random challenge, called a nonce,
   plus the salt and iteration count stored in the verifier.
3. Client uses the nonce, salt and iteration count to derive a keyed proof
   from the user-supplied password and sends it to the server.
4. Server computes the expected proof from the stored verifier and compares.
   If they match, the user is authenticated.
5. Server sends a final message the client can verify, proving the server
   also knows the verifier. This is mutual authentication: the client knows
   it is talking to the real server, not an impostor.

### What is stored in the LDAP userPassword attribute

Not the plaintext password. The SCRAM verifier: a salted, iterated hash
derived from the password. Format:

    {SCRAM-SHA-256}iter,salt,StoredKey,ServerKey

The server can verify a correct password against this without ever knowing
the plaintext. DIGEST-MD5 cannot do this. That is the entire point.

### SCRAM-SHA-256 vs SCRAM-SHA-512

These are the same authentication protocol, with SCRAM-SHA-512 using a longer
hash. The only difference is the hash function used to derive the keys and
proof. As SHA-512 produces a longer hash, it is computationally harder to
brute-force. SCRAM-SHA-512 is an OpenLDAP extension not yet in an RFC. Both
store their verifiers in the same `userPassword` attribute as separate values,
one per mechanism:

    userPassword: {SCRAM-SHA-256}iter,salt,StoredKey,ServerKey
    userPassword: {SCRAM-SHA-512}iter,salt,StoredKey,ServerKey

`slapd`, when authenticating, picks up the appropriate attribute value for
the mechanism the client selected.

## How GSSAPI Works

GSSAPI (Generic Security Services API, RFC 4752) is the SASL wrapper around
Kerberos 5. The client obtains a Kerberos ticket from the KDC and presents it
to `slapd` as proof of identity. No password is sent. No password is stored
in LDAP. `slapd` verifies the ticket against its keytab file.

The exchange:

1. Client obtains a Kerberos service ticket for the LDAP service from the KDC.
2. Client sends the ticket to `slapd` via the GSSAPI exchange.
3. `slapd` verifies the ticket using its keytab (`/etc/krb5.keytab` or
   `/etc/ldap/ldap.keytab`).
4. If valid, the client is authenticated as the Kerberos principal in the ticket.
5. Mutual authentication: the server also proves its identity to the client.

GSSAPI requires:
- A Kerberos KDC with the user enrolled
- A service principal for LDAP (`ldap/ldap.marsel.is@MARSEL.IS`)
- A keytab on the `slapd` host containing that service principal's key

No passwords in LDAP. No `sasldb2`. No secondary database. This is why
GSSAPI is the correct long-term answer.

## How EXTERNAL Works

EXTERNAL is not a password mechanism. It uses the TLS client certificate as
the authentication credential. When the client connects, it presents a client
certificate during the TLS handshake as the authentication token. `slapd`
reads the subject DN from that certificate and uses it as the authenticated
identity. No password is exchanged and there is no challenge-response.
The cert is the credential. EXTERNAL is used for authentication only: it
establishes identity from the cert and nothing else. Encryption and integrity
are provided by the TLS layer, not by EXTERNAL.

The name EXTERNAL is a misnomer. It refers to the fact that the credential
comes from outside SASL itself (specifically, from the TLS layer) and not
to what the mechanism does. A more descriptive name would be `TLSCERT` or
`X509`.

This mechanism requires the client to have a certificate issued by a CA that
the server trusts (`TLS_CACERT` in `ldap.conf` / `TLSCACertificateFile` in
`slapd.conf`). If the cert is valid and trusted, the client is authenticated
as the subject DN in the cert.

## How DIGEST-MD5 Works (and Why It Is Broken)

DIGEST-MD5 is a challenge-response protocol. The server generates a random
challenge; the client combines the challenge with the plaintext password using
MD5 and sends the result. The server does the same computation and compares.

The problem: for the server to verify the response, it must know the plaintext
password. LDAP stores passwords hashed. Hashes are one-way. DIGEST-MD5 cannot
use LDAP's `userPassword`.

The "solution" is `sasldb2`: a separate Berkeley DB file storing the same
passwords in cleartext, maintained manually with `saslpasswd2`. No sync with
LDAP. A user can have a different password in each store with no warning.

DIGEST-MD5 was deprecated in RFC 6331 (2011). Do not use it.
Do not use `sasldb2` for anything.

### saslpasswd2

`saslpasswd2` is the tool used to add users to `sasldb2`. It stores both the
username and the password in the database. The password is stored in cleartext.
It has no connection to LDAP's `userPassword`. A user can have a completely
different password in `sasldb2` than in LDAP with no warning and no enforcement.

    saslpasswd2 -c -u example.com matt   # create user matt in realm example.com

This is only relevant if you are using DIGEST-MD5, which you should not be.

## How CRAM-MD5 Works

CRAM-MD5 (Challenge-Response Authentication Mechanism, RFC 2195) is similar
to DIGEST-MD5: the server sends a challenge, the client hashes it with the
password using HMAC-MD5 and replies. The server verifies.

Same problem as DIGEST-MD5: requires plaintext or reversibly encrypted
passwords on the server. Also has no mutual authentication -- the client
cannot verify it is talking to the real server. Vulnerable to offline
dictionary attacks against captured challenge-response pairs.

Superseded by SCRAM. Do not use.

## How OTP Works (and Why It Is Not TOTP)

OTP (One-Time Password, RFC 2444) is based on S/KEY: a hash chain derived
from a seed and a passphrase. Each authentication consumes one value from
the chain. Once the chain is exhausted, it must be regenerated.

OTP has nothing to do with TOTP (Time-based One-Time Password, RFC 6238),
which is what Google Authenticator, Authy and similar apps use. TOTP is not
a SASL mechanism. OTP predates TOTP by a decade and works completely
differently.

OTP is practically undeployed. No major directory service uses it. Listed
here for completeness.

## How NTLM Works (and Why to Avoid It)

NTLM (NT LAN Manager) is Microsoft's proprietary challenge-response
authentication protocol. The server sends a challenge; the client responds
using an NT hash of the password.

Problems:

- Pass-the-hash: an attacker who captures the NT hash can authenticate
  without knowing the plaintext password.
- Relay attacks: NTLM responses can be relayed to other services.
- No mutual authentication in NTLMv1.
- Microsoft itself deprecated NTLM in favor of Kerberos.

NTLM has no business in a Unix LDAP stack. Do not advertise it.

## Why DIGEST-MD5 requires sasldb2 (and why that is a disaster)

DIGEST-MD5 is a challenge-response protocol. The server generates a challenge;
the client hashes the password with it and sends the response. For the server
to verify the response it must be able to reproduce the expected hash, which
requires knowing the original plaintext password.

LDAP stores passwords hashed (SSHA, bcrypt, etc). Hashes are one-way -- the
server cannot reverse them. So DIGEST-MD5 cannot use LDAP's `userPassword`.

The "solution" is `sasldb2`: a separate Berkeley DB file where the same user
passwords are stored again, in cleartext, maintained manually with `saslpasswd2`.
No sync with LDAP. No automation. Two password stores, one of them cleartext,
kept in sync by hand. A user can have a different password in each store with
no warning and no enforcement.

This is why DIGEST-MD5 was deprecated (RFC 6331, 2011). Do not use it.
Do not use `sasldb2` for anything.

SCRAM solves this correctly: the server stores a salted hash (the SCRAM verifier)
in LDAP's `userPassword` attribute. One store, no cleartext, no manual sync.

## Combos That Make Sense

### SCRAM-SHA-256, SCRAM-SHA-512

Safest password auth mechanism to use, without using Kerberos itself. Both
use salted challenge-response: the password is never sent over the wire and
is stored as a salted verifier in the `userPassword` attribute in LDAP, not
in cleartext. SHA-512 is preferred; SHA-256 is the fallback for clients that
do not support SHA-512. `slapd` advertises both and the client picks the
strongest it supports. No second password store, no cleartext. Since there
are no cryptographically weak mechanisms such as DIGEST-MD5 and CRAM-MD5,
we avoid a downgrade-the-algorithm attack surface.

### GSSAPI, EXTERNAL

Kerberos and TLS client cert. Strongest possible. No passwords anywhere.
Requires both a Kerberos KDC and a PKI.

### PLAIN over TLS 1.3 only

Acceptable in controlled environments where TLS 1.3 is enforced at the
transport layer (`security tls=256` in `slapd.conf`). Simple to implement
and debug. Only offer if TLS is mandatory; never alongside unencrypted
connections.

### SCRAM-SHA-256, GSSAPI

Use this when you are migrating users to Kerberos but have not finished the
work yet. Users already enrolled in Kerberos authenticate via GSSAPI. Users
not yet in Kerberos authenticate via SCRAM-SHA-256, with the password verifier
stored in the `userPassword` attribute in LDAP. Once all users are in Kerberos,
remove SCRAM-SHA-256 from the mechanism list and remove the `userPassword`
attribute entirely from all entries.

### SCRAM-SHA-256, SCRAM-SHA-512, GSSAPI

Full transition stack. `slapd` accepts all three mechanisms. Users in Kerberos
authenticate via GSSAPI and never touch SCRAM. Users not yet in Kerberos get
both SCRAM mechanisms: SHA-512 if the client supports it, SHA-256 as fallback.
Once all users are in Kerberos, remove both SCRAM mechanisms from the list
and remove the `userPassword` attribute entirely from all entries.

### EXTERNAL, SCRAM-SHA-256

Cert auth preferred; SCRAM fallback for clients without client certs.
Reasonable during PKI rollout before all clients have certs.

## Combos That Make Less Sense

### SCRAM-SHA-1, anything

SHA-1 is weaker than SHA-256. No reason to advertise it if SHA-256 is available.
Offering it widens the attack surface for no gain.

### PLAIN, SCRAM-SHA-256

Redundant. SCRAM already handles password auth securely. PLAIN adds attack
surface without adding capability. Described here as a warning against use.

### GSSAPI, DIGEST-MD5

Listed here as a warning against use. GSSAPI is strong; DIGEST-MD5 is
cryptographically broken. When `slapd` advertises both, a client or attacker
can request DIGEST-MD5 instead of GSSAPI, forcing an algorithm downgrade to
the broken mechanism. The server will comply because it advertised DIGEST-MD5
as acceptable. The presence of a strong mechanism in the list does not protect
against downgrade if a weak mechanism is also listed. Do not advertise
DIGEST-MD5, or any other cryptographically weak mechanism, under any
circumstances.

### EXTERNAL alone

No password fallback. Anyone without a client cert is locked out.
Operationally fragile -- a single cert expiry or loss locks the account.
Acceptable only in tightly controlled environments with robust cert lifecycle
management.

## slapd.conf: sasl-secprops

# sasl-secprops controls which mechanisms slapd will offer and minimum security requirements.
# Format: comma-separated list of properties.
#
# Properties:
#   noanonymous        do not allow anonymous (no-credential) SASL binds
#   noplaintext        do not allow plaintext (PLAIN/LOGIN) mechanisms
#   noactive           do not allow mechanisms vulnerable to active attacks (DIGEST-MD5, CRAM-MD5)
#   nodictionary       do not allow mechanisms vulnerable to dictionary attacks
#   forward_secrecy    require forward secrecy (mechanisms that provide PFS)
#   minssf=N           minimum SSF the SASL layer must provide (0=none, 256=AES-256)
#   maxssf=N           maximum SSF the SASL layer may provide
#   maxbufsize=N       maximum SASL buffer size (default 65536)
#
# For our setup (SCRAM-SHA-256/512, GSSAPI, no plaintext, no broken mechanisms):
sasl-secprops noanonymous,noplaintext,noactive,nodictionary,minssf=0
#
# minssf=0 because the security directive in slapd.conf already enforces
# ssf=256 at the connection level before SASL runs. There is no need for
# the SASL layer to re-enforce the same requirement, though it is not
# unheard of.
#
# To restrict which mechanisms are offered, use mech_list in /etc/sasl2/slapd.conf:
# (not a slapd.conf directive -- controlled via the Cyrus SASL config file)
# authz-regexp uses POSIX extended regex (ERE, same as grep -E, via POSIX regex.h).
#
# /etc/sasl2/slapd.conf:
#   mech_list: SCRAM-SHA-512 SCRAM-SHA-256 GSSAPI

## It Is 2026: Why Are We Still Negotiating?

SASL's mechanism negotiation made sense in 1997 when nobody agreed on
anything and every site ran something different. In 2026 there are two
correct answers: GSSAPI if you have Kerberos, SCRAM-SHA-512 if you do not.
Everything else in the mechanism list is either broken, obsolete or a
footgun waiting to be pulled.

The negotiation framework is fine. The forty-year accumulation of mechanisms
it hosts is not. A well-configured server in 2026 should advertise at most
two mechanisms and reject everything else at the configuration level, not
leave it up to the client to "pick the strongest it supports" while quietly
also offering DIGEST-MD5 because nobody cleaned up the config file.
