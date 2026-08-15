# Chapter 8 lab: Docker Compose (v2)

Provenance marked per section: [BOOK p.N] follows the chapter's own walkthrough,
[CLAUDE] is added material and says why it is there.

Host: docker.marsel.is (10.0.0.7). Run the CLI ON the host, not via the
dockervm context from molly: the stack uses relative bind mounts and ${PWD},
both daemon-side. [CLAUDE, split-host note; the book assumes one machine]

```
ssh gmarselis@docker.marsel.is
cd ~/src/rocketchat-hubot-demo
```

Already cloned. Book pages below are book numbering.

---

## Part 1: prepopulate the data volume [BOOK p.199]

What this demonstrates: Compose can create empty volumes but not populated
ones. The chapter's stack needs a preinitialized MongoDB, so the gap is
closed by hand before Compose is ever run: an ephemeral container mounts the
target volume plus the backup dir, untars, exits. The volume outlives it.

The book does this BEFORE first compose contact. The tarball is in
mongodb/data_volume_image, not in compose/.

```
docker volume create mongodb-rocketchat

cd mongodb/data_volume_image
docker run --rm \
    -v mongodb-rocketchat:/bitnami/mongodb \
    -v ${PWD}:/backup busybox \
    tar -xzvf /backup/mongodb-rocketchat.tgz -C /bitnami/mongodb
cd ../..
```

[CLAUDE, one check the book skips] Look at what actually landed, so "volume
prepopulation" is files you have seen and not an incantation:

```
docker run --rm -v mongodb-rocketchat:/data busybox ls -la /data
```

## Part 2: config, build, up [BOOK p.200-201]

What this demonstrates: the chapter's core claim, one YAML file replaces the
forty-line shell_deploy.sh from its opening. config validates before the
daemon is touched, build handles only services with build:, up creates
network, containers and startup ordering in one command.

```
cd compose
docker compose config
docker compose build
docker compose up -d
```

Book's expected up output: network compose_botnet created, mongodb goes
Healthy (~60s, the healthcheck gate), THEN rocketchat/zmachine/hubot start.
Watch for that ordering: it is depends_on condition: service_healthy doing
its startup-only job.

Project prefix: everything is named compose-* because the directory is
compose/. [BOOK p.201]

[CLAUDE, deliberate breaks; the book only shows the error output on p.200,
never makes you cause it] Break config twice, fix after each:

```
# 1. schema break: add a bogus key under services.mongodb, e.g. builder: yes
docker compose config
# expect: services.mongodb Additional property builder is not allowed

# 2. reference break: point mongodb at a volume name not declared in volumes:
docker compose config
```

Both caught before the daemon is touched. A wrong VALUE inside environment:
is not: that is the validation boundary.

## Part 3: is it up [BOOK p.201-202]

What this demonstrates: the two commands the book calls the most useful for
troubleshooting, logs here, exec in Part 4. Stack-scoped rather than
host-scoped: this is the Compose delta over plain docker logs.

```
docker compose logs
docker compose logs rocketchat | grep "SERVER RUNNING"
```

Color-coded per service, interlaced by arrival time.

[CLAUDE, split-host consequence] The book now says browse to
http://127.0.0.1:3000. That is molly-side wrong: the port is published on
docker.marsel.is, so browse http://docker.marsel.is:3000 or tunnel. First-run
wizard: admin user, then the general channel. Optional: type into the zmachine
channel and play a turn of the game via hubot, which proves hubot -> zmachine
-> back through rocketchat, the whole service-name DNS chain, from the UI.

## Part 4: exercising the stack [BOOK p.205-206]

What this demonstrates: the book's "Exercising Docker Compose" section by
name. Familiar docker commands re-scoped to the stack: top and exec take a
SERVICE name resolved from the compose file in the current directory, not a
container name, and lifecycle commands work per-service or whole-stack.

The book's own sequence:

```
docker compose top
docker compose exec mongodb bash
```

Inside: the prompt is "I have no name!" because uid 1001 has no /etc/passwd
entry in the bitnami image. Run mongosh, poke, exit. [BOOK p.206]

```
docker compose stop zmachine
docker compose start zmachine
docker compose pause
docker compose unpause
```

[BOOK p.206, per-service stop/start and whole-stack pause]

[CLAUDE, closes the loop on the ch8 cheatsheet DNS entry] While it is up,
prove service-name resolution from inside rather than trusting the YAML:

```
docker compose exec hubot sh -c 'getent hosts mongodb zmachine rocketchat'
```

## Part 5: interpolation, defaults, mandatory [BOOK p.207-209]

What this demonstrates: the chapter's "Managing Configuration" section. The
same stack made configurable without editing the file: interpolation
borrowed from the shell, a default for the common case, a hard failure for
the value that must not have one. config is the verification tool
throughout, nothing needs to start.

The book ships three compose files as a progression: hardcoded password ->
default via ${VAR:-} -> mandatory via ${VAR:?}. Walk it with config, no
containers needed:

```
docker compose -f docker-compose-defaults.yaml config | grep ROCKETCHAT_PASSWORD
HUBOT_ROCKETCHAT_PASSWORD="my-unique-pw" \
    docker compose -f docker-compose-defaults.yaml config | grep ROCKETCHAT_PASSWORD
docker compose -f docker-compose-env.yaml config
HUBOT_ROCKETCHAT_PASSWORD=1234567 \
    docker compose -f docker-compose-env.yaml config | grep ROCKETCHAT_PASSWORD
```

The mandatory failure is the error you already hit before the lab, and note
the variable-name trap you also already hit: the YAML key is
ROCKETCHAT_PASSWORD, the interpolated variable is HUBOT_ROCKETCHAT_PASSWORD.
The right-hand side of ${} is what must exist in the environment. [BOOK p.209,
trap yours]

The book's margin note on p.208: an EMPTY variable equals unset under :-,
use ${VAR-default} when empty string is a valid value.

[CLAUDE, extends the book's p.208 margin note into something you can see]
Prove that distinction once, because it is invisible until it bites:

```
HUBOT_ROCKETCHAT_PASSWORD= docker compose -f docker-compose-defaults.yaml config \
    | grep ROCKETCHAT_PASSWORD     # empty -> default wins under :-
```

[CLAUDE, extends the book's p.209 "we will address that in a few minutes"]
The book acknowledges the password is now visible in the process list and
defers the fix to its secrets section. The .env file is the interim mechanism
and its traps are in the cheatsheet: not a shell script, no quotes, ambient
pickup. One drill, five minutes:

```
echo 'HUBOT_ROCKETCHAT_PASSWORD=1234567' > .env
docker compose -f docker-compose-env.yaml config | grep ROCKETCHAT_PASSWORD
echo 'HUBOT_ROCKETCHAT_PASSWORD="1234567"' > .env
docker compose -f docker-compose-env.yaml config | grep ROCKETCHAT_PASSWORD
rm .env
```

Second output keeps the quotes. That is the trap, seen once, done.

[CLAUDE, precedence drill; the book states the order on p.210 but never
stacks all three layers at once] Same variable in all three places, check
with config at each step:

```
# layer 1: the YAML default only (:-bot-pw! in docker-compose-defaults.yaml)
rm -f .env
docker compose -f docker-compose-defaults.yaml config | grep ROCKETCHAT_PASSWORD

# layer 2: .env beats the YAML default
echo 'HUBOT_ROCKETCHAT_PASSWORD=envfile-pw' > .env
docker compose -f docker-compose-defaults.yaml config | grep ROCKETCHAT_PASSWORD

# layer 3: shell beats .env
HUBOT_ROCKETCHAT_PASSWORD=shell-pw \
    docker compose -f docker-compose-defaults.yaml config | grep ROCKETCHAT_PASSWORD

rm .env
```

Expected: bot-pw!, envfile-pw, shell-pw. YAML default < .env < shell.

## Part 6: override file [CLAUDE, not in the chapter]

The book mentions override files in one sentence and never demonstrates.
This is here because it is the exact mechanism for INSaFLU: their compose
file stays pristine, our changes live beside it. This is the INSaFLU
rehearsal, five minutes.

Create docker-compose.override.yml next to docker-compose.yaml:

```yaml
services:
  zmachine:
    ports:
      - "8081:80"
  mongodb:
    restart: "no"
```

```
docker compose config | grep -A3 'zmachine:\|mongodb:'
```

Confirm: picked up with no flag (filename convention), ports APPENDED
(zmachine gains 8081, keeps expose), restart REPLACED (scalar). That is the
whole merge model: maps merge, lists append, scalars replace.

```
rm docker-compose.override.yml
```

## Part 7: teardown [BOOK p.206 + p.199 margin note]

What this demonstrates: down removes what Compose owns (containers,
network) and leaves what it does not (the external volume). The boundary of
the stack's lifecycle, seen once.

```
docker compose down
docker volume ls | grep rocketchat
```

Volume survives: external to the stack's lifecycle, and the book's p.199
margin note says you can keep it or docker volume rm it to start fresh.
Network is gone. [CLAUDE, one sentence] That asymmetry is the right default:
the network is structure, the volume is data.

---

## Findings to record

- The up ordering you observed: how long mongodb took to go Healthy, and
  that nothing else started before it.
- The variable-name trap, in your own words.
- Which override keys merged and which replaced.
- Anything Docker 29.7.1 / containerd store did differently from the book's
  2023 output.
