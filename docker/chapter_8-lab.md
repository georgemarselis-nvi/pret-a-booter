# Chapter 8 lab: Docker Compose

Host: docker.marsel.is (10.0.0.7). Run the CLI ON the host, not via the
dockervm context from molly. Chapter 8 uses relative bind mounts
(`../zmachine/saves`) and `${PWD}`, both of which resolve daemon-side. The repo
tree must be where the daemon is.

```
ssh gmarselis@docker.marsel.is
git clone https://github.com/spkane/rocketchat-hubot-demo.git \
    --config core.autocrlf=input
cd rocketchat-hubot-demo/compose
```

---

## Part 1: read before running

```
docker compose config
```

Prints the fully resolved file. Compare it against `docker-compose.yaml` by eye.
Note what changed: `version:` warning, relative paths made absolute, `${VAR}`
substituted, short-form ports expanded to long form.

Break it deliberately, then fix it:

```
# add a bogus key under services.mongodb, for example: builder: yes
docker compose config
```

Expected: `services.mongodb Additional property builder is not allowed`, with
file and line. This is schema validation before the daemon is touched.

Second break, reference rather than schema:

```
# point the mongodb service at a volume name that does not exist in volumes:
docker compose config
```

Note that this one is also caught, and that a wrong *value* inside an
environment variable is not.

---

## Part 2: volume prepopulation

The stack expects a preinitialized MongoDB. Compose cannot make one.

```
docker volume create mongodb-rocketchat

docker run --rm \
    -v mongodb-rocketchat:/bitnami/mongodb \
    -v ${PWD}:/backup busybox \
    tar -xzvf /backup/mongodb-rocketchat.tgz -C /bitnami/mongodb

docker volume inspect mongodb-rocketchat
docker run --rm -v mongodb-rocketchat:/data busybox ls -la /data
```

Confirm in the compose file that this volume is declared `external: true`, and
predict before running: after `docker compose down`, does the volume survive?
Then check.

---

## Part 3: up, and what got named

```
docker compose build
docker compose up -d
docker compose ps
docker network ls | grep -i compose
docker volume ls
```

Observe the project prefix from the directory name: `compose-mongodb-1`,
`compose_botnet`. Then prove where it comes from:

```
docker compose down
docker compose -p zork up -d
docker compose -p zork ps
docker compose -p zork down
```

Same file, different names. Note that `-p` must be repeated on every command,
which is why `name:` in the file is better.

---

## Part 4: the observation pass

```
docker compose logs
docker compose logs mongodb
docker compose logs -f hubot
docker compose top
docker compose exec mongodb bash
```

Inside the mongodb container: `id`, `whoami`, `cat /etc/passwd | tail`. The
prompt says `I have no name!` because uid 1001 has no passwd entry in the
bitnami image. Confirm the uid matches what the host sees in `docker compose
top`.

Then verify service-name DNS, which is the whole point of the network section:

```
docker compose exec hubot sh -c 'getent hosts mongodb; getent hosts zmachine'
docker compose exec hubot sh -c 'wget -qO- http://zmachine:80/ ; echo'
```

`zmachine` uses `expose:` not `ports:`, so this must succeed from inside and
fail from the host:

```
curl http://localhost:80        # expect failure or the wrong service
```

---

## Part 5: depends_on and health

```
docker inspect --format '{{json .State.Health}}' compose-mongodb-1 | jq
docker compose ps
```

Find the `condition: service_healthy` in the file and connect it to what you
just printed. Then test the boundary of the claim: kill mongodb and watch what
Docker does and does not do about the services that depend on it.

```
docker compose stop mongodb
docker compose ps
docker compose logs --tail 20 rocketchat
docker compose start mongodb
```

Expected finding: dependents were not restarted, not stopped, not held. The
condition applies at startup only.

---

## Part 6: interpolation and .env

Use the alternate file the chapter ships:

```
docker compose -f docker-compose-env.yaml config | grep -i password
```

Expect the mandatory-variable failure:
`required variable HUBOT_ROCKETCHAT_PASSWORD is missing a value`.

Now walk the three layers, checking with `config` at each step and never
starting a container:

```
# 1. nothing set
docker compose -f docker-compose-env.yaml config | grep -i password

# 2. .env only
echo 'HUBOT_ROCKETCHAT_PASSWORD=1234567' > .env
docker compose -f docker-compose-env.yaml config | grep -i password

# 3. shell wins over .env
HUBOT_ROCKETCHAT_PASSWORD=shellvalue \
    docker compose -f docker-compose-env.yaml config | grep -i password
```

Then the quoting trap:

```
echo 'HUBOT_ROCKETCHAT_PASSWORD="1234567"' > .env
docker compose -f docker-compose-env.yaml config | grep -i password
```

The quotes are part of the value. `.env` is not a shell script.

Then the ambient-pickup trap: rename the file and confirm the variable vanishes
without any change to the YAML or the command line.

```
mv .env .env.disabled
docker compose -f docker-compose-env.yaml config | grep -i password
rm -f .env.disabled
```

Finally, the default-form distinction. Edit a value in the file to each form in
turn and run `config` with the variable set to empty string:

```
VAR=  ${VAR:-default}    # default wins, empty is treated as unset
VAR=  ${VAR-default}     # empty string wins
```

---

## Part 7: override file (the INSaFLU rehearsal)

Do not edit `docker-compose.yaml`. Create `docker-compose.override.yml` beside
it:

```yaml
services:
  mongodb:
    environment:
      LAB_MARKER: "chapter8"
  zmachine:
    ports:
      - "8081:80"
```

Then:

```
docker compose config | grep -A5 -i 'lab_marker\|8081'
```

Confirm three things in the resolved output:

1. It was picked up with no flag, because of the filename.
2. `environment` merged rather than replaced: the original variables are still
   there alongside `LAB_MARKER`.
3. `ports` appended: zmachine now has a published port it did not have, and its
   `expose` is untouched.

Then prove the explicit form is equivalent:

```
docker compose -f docker-compose.yaml -f docker-compose.override.yml config \
    | diff - <(docker compose config)
```

Now a replacing key rather than a merging one. Add to the override:

```yaml
services:
  mongodb:
    restart: "no"
```

Check `config`: scalar replaced, not appended. This is the merge rule that
matters when you write the real override against INSaFLU.

---

## Part 8: teardown, and what is left

```
docker compose down
docker volume ls | grep rocketchat
docker network ls | grep compose
```

Volume still there, because `external: true`. Network gone. Explain to yourself
why that asymmetry is the right default.

Cleanup:

```
docker compose down --rmi local
docker volume rm mongodb-rocketchat
rm -f .env docker-compose.override.yml
```

---

## Findings to record

- Whether `depends_on: condition: service_healthy` did anything at all after
  startup (predicted: no).
- The exact precedence result from Part 6, in your own words.
- Which override keys merged and which replaced.
- Anything that behaved differently on Docker 29.7.1 with the containerd image
  store than the 2023 book describes.
