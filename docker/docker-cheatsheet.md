# Docker cheatsheet: chapter 5, working with containers

## VM or container
How many will exist, and does killing one at random cost anything?
  many + no   -> container
  one  + yes  -> VM
VM when the service is a long-lived identity: fixed IP someone else
whitelists, own hostname and certificate, own kernel or SELinux
policy, must be up independent of a scheduler.
Container when it is one process with declared inputs, disposable,
or when the build artifact is the point.
"Stateless" is not "holds no data". A back-ldap proxy holds no data
but has identity. Identity is what makes it a VM.

## create vs start vs run
docker container create   build config from image, do not execute
docker container start    execute an existing container
docker container run      create + start in one command
Options that shape the container belong to create and run, not start.

## Identity
--name="awesome-service"        one container per name per host
-l key=value                    label, repeatable
docker container ls -a -f label=deployer=Ahmed
docker container inspect <name>        shows labels and everything else
Containers inherit all labels from the parent image.
Hashes: full is 64 chars, short is the first 12. Any unambiguous
prefix works: docker container start 092

## Hostname and DNS
--hostname="mycontainer.example.com"
--dns=8.8.8.8 --dns=8.8.4.4
--dns-search=example1.com
--dns-search=.                  leave search domain unset
Default hostname is the container ID, not fully qualified.
/etc/hostname, /etc/hosts and /etc/resolv.conf are bind mounts from
copies the daemon prepares under /var/lib/docker/containers.

## MAC
--mac-address="a2:11:aa:22:bb:33"
Default prefix 02:42:ac:11. Only set it to avoid collision with
another virtualization layer on the same private block. Duplicate
MACs cause ARP contention. Stay in the locally administered ranges:
x2, x6, xA, xE as the second hex digit.

## Volumes
--mount type=bind,target=/mnt/session_data,source=/data
-v /mnt/session_data:/data              same thing, shorter
-v /mnt/session_data:/data:ro           that mount read-only
--mount type=bind,...,readonly          same
--read-only=true                        container ROOT fs read-only
--mount type=tmpfs,destination=/tmp,tmpfs-size=256M
Fully qualified paths required. Neither end must preexist; a missing
host path is created as a DIRECTORY, which breaks file mounts.
Volumes are rw by default.
--read-only=true and :ro are independent. Combine --read-only=true
with a writable -v to confine all writes to the volume.
tmpfs is in-memory, counts against system memory, lost on stop.
Paths are resolved by the DAEMON. With a remote context, -v /etc
means the daemon host's /etc.

## SELinux mount flags
:z   shared label, multiple containers may access
:Z   private, exact MCS label for this container only
Both relabel the HOST path, recursively.
:Z on /etc or /var renders the host inoperable and needs manual
relabeling. No-op on Debian (AppArmor). Live on EL with SELinux
enforcing.

## CPU
--cpu-shares 512        relative weight, 1024 = full pool, default
--cpuset-cpus=0         pin to cores; 0-2 and 0,2,4 and 0-2,4 all valid
--cpus="1.5"            hard ceiling, 0.01 to core count
--cpu-quota             raw CFS quota, superseded by --cpus
docker container update --cpus="1.5" <id> <id>
Shares are a hint, not a reservation: the ratio is computed only
among containers contending for the SAME cores. Two containers on
core 0 with 512 and 1024 split it one third to two thirds. On an idle
box a share limit has no visible effect. Zero-indexed; a nonexistent
core gives "Cannot start container".
--cpus is absolute: 1.5 cores per period, throttled even when idle.
Docker counts CPUs as Linux does, from /proc/cpuinfo, so hyperthreads
count as cores.

## Memory
--memory 512m           b, k, m, g. Sets RAM AND swap when used alone
--memory-swap 768m      total memory plus swap
--memory-swap -1        unlimited swap
--memory-swap == --memory   no swap at all
Memory is a HARD limit, unlike CPU shares. Exceeding it invokes the
OOM killer inside the cgroup. Telltale signs: exit code 137, dmesg
OOM output on the daemon host, and a container oom line in
docker system events.
--oom-kill-disable and --oom-score-adj exist; do not use them.

## Block I/O
--blkio-weight          10 to 1000, default 500, 0 disables
--blkio-weight-device   same, per device
--device-read-bps       /dev/vda:5mb
--device-write-bps
--device-read-iops      /dev/vda:256
--device-write-iops
Weights behave like CPU shares and are hard to tune. The book
recommends the iops limits.

## ulimits
dockerd --default-ulimit nofile=50:150      daemon-wide default
--ulimit nofile=150:300                     per container override
ulimit -a lists what can be constrained. Predates cgroups, still
useful.

## Kernel support
docker system info      warns if the kernel lacks a capability, e.g.
                        WARNING: No swap limit support
Constraints are applied at creation. Change them with
docker container update or redeploy.

## Restart
--restart=no                default
--restart=always            even if deliberately stopped before reboot
--restart=unless-stopped    not if you stopped it yourself
--restart=on-failure        nonzero exit only
--restart=on-failure:3      give up after three attempts
On reboot the daemon restarts containers that have a policy, provided
the docker service itself is enabled in systemd.
Wrapping docker run in a systemd unit is the alternative: gives
ordering and journal integration, but then set --restart=no or the
two fight over ownership.

## Stopping and killing
docker container stop <id>          SIGTERM, then SIGKILL after 10s
docker container stop -t 25 <id>    change the grace period
docker container kill <id>          immediate
docker container kill --signal=USR1 <id>
Stopped is not paused: the process exits. Config, filesystem, env
vars and port bindings survive; tmpfs and memory do not. Restart with
start, no re-create needed.
Signals from the host land normally. Inside the container, signals
with default actions sent to PID 1 are dropped unless the process
installed a handler, which is why a shell entrypoint often ignores
SIGTERM and eats the full grace period.

## Pause
docker container pause <id>
docker container unpause <id>
cgroup freezer: descheduled, memory and process table entries kept,
no signal delivered so the process never learns. ls still shows Up.

## Cleanup
docker container rm <id>            stop it first, or use -f
docker image rm <id>                fails with Conflict if in use
docker system prune                 stopped containers, unused
                                    networks, dangling images, build
                                    cache
docker system prune -a              all unused images, not just
                                    dangling
docker container rm $(docker container ls -a -q)
docker container rm $(docker container ls -a -q --filter 'exited!=0')
docker image rm $(docker images -q -f "dangling=true")
Worth running prune on a systemd timer on busy hosts.

## Isolation
One-way. The container cannot see the host; the host sees everything.
From the host, list a container's filesystem:
  docker inspect --format '{{.State.Pid}}' <name>
  ls /proc/<pid>/root/etc
Or: nsenter -t <pid> -m -- ls /etc

## Gotchas
Everything after the image name goes to the container command, not to
docker. In the book's examples that is stress: --cpu N burners,
--vm N --vm-bytes 128M memory hogs, --io N sync spinners,
--timeout Ns.
docker system events, not docker service events. It blocks and
streams: run it in one terminal, trigger the event in another.
Default user inside the container is root; --user changes it.

# Docker cheatsheet: chapter 6, exploring Docker

## Version and info
docker version          client and server component versions, API
                        version and daemon minimum (e.g. 1.55, min
                        1.40). Client negotiates down to the daemon
                        API on connect; a field the old daemon does
                        not know inside a valid request is silently
                        ignored. Keep client and daemon matched.
                        Server unreachable: prints client block only.
docker system info      daemon state and environment: storage driver,
                        cgroup version, kernel, OS, runtimes (runc
                        default), plugin list (volume, network, log
                        drivers), container and image counts, warnings
                        about missing kernel capabilities.
Version answers "what am I running", info answers "what is this host
and what can it do". Neither names the endpoint host:
docker context ls / docker context inspect dockervm for that.
dockerd --data-root     move /var/lib/docker elsewhere; permanent
                        form belongs in /etc/docker/daemon.json.

## Pulling
docker image pull ubuntu:latest
latest is a convention, not a guarantee: it is whatever the publisher
last tagged, moves without notice, and Docker never auto-updates a
local copy. Production deploys pin a version tag, or better the
content digest:
docker image pull ubuntu@sha256:b6b83d...
Digest pulls require the FULL hash, no prefix shortening.

## Inspect
docker container inspect <id|name>
Id: container identifier, random at creation, 64 hex chars, any
unambiguous prefix accepted, short form is first 12.
Image: content-addressed sha256 digest of the image the container was
created from. One image per container, always a single digest; the
image's layers have their own digests but live in
docker image inspect under RootFS.Layers, not here. Multi-platform
manifests resolve to the digest of the one platform image used.
Also in inspect: Config.Env, Cmd, Hostname, Created (precise),
State.Pid (host PID, feeds nsenter).

## Exec and nsenter
docker container exec -it <id> /bin/bash
New process inside all of the container's namespaces and cgroups, via
the daemon. -d runs it backgrounded: debugging only, since anything
the deployment depends on belongs in the image. To signal the main
process instead: docker container kill -s <SIGNAL>.
A container runs ONLY what you asked for: no init, no background
services. ps -ef inside shows the entrypoint as PID 1 and nothing
else.
nsenter: enters a running process's namespaces directly via the
kernel. Needs a container already running and its main PID:
  docker inspect --format '{{.State.Pid}}' <name>
  nsenter -t <pid> -m -p /bin/bash
vs exec: works with the daemon dead (running containers survive it,
parented by containerd-shim), selective (-n = network only, keep host
fs and tools), any process not just Docker. Cannot start anything.
Skips cgroups. Needs root. Covered properly at p328.

## Returning a result
Foreground run, no TTY: stdin, stdout, stderr and the exit code proxy
to the local terminal.
docker container run --rm ubuntu /bin/false; echo $?   -> 1
Pipes run LOCALLY unless quoted into a remote shell:
  ... /bin/cat /etc/passwd | wc -l      wc runs on molly
  ... bash -c "cat /etc/passwd | wc -l" wc runs in the container

## Volumes
docker volume create my-data
docker volume ls / inspect / rm
Named volumes are daemon-managed directories at
/var/lib/docker/volumes/<name>/_data on the daemon host. No size
limit: they grow until the disk (vdb) is full. Bind mounts never
appear in docker volume ls.
Attach: --mount source=my-data,target=/app
Data persists across containers; mount the same volume elsewhere and
the files are there.
rm of an in-use volume fails with "volume is in use" listing holder
container IDs, including STOPPED containers hidden from plain ls: rm
the container first (docker container ls -a to find it).

## Logging
Default driver json-file: daemon captures stdout and stderr, one JSON
file per container at
/var/lib/docker/containers/<id>/<id>-json.log
(fields: log, stream, time).
docker container logs <name>
  -f            follow
  --since       RFC3339, unix ts, or Go duration (5m45s)
  --tail N
Rotation is NOT enabled by default: set --log-opt max-size and
max-file (max-file inert without max-size) in daemon.json for
production. After rotation, logs command reads current file only.
Other drivers: syslog, journald, fluentd, gelf, awslogs, splunk,
gcplogs, local. ONE driver at a time; anything except json-file or
journald KILLS docker container logs unless the plugin keeps a local
copy.
syslog driver over TCP/TLS blocks container START if the log server
is unreachable: use UDP and accept lossy delivery, or non-blocking
mode: --log-opt mode=non-blocking --log-opt max-buffer-size=4m
(drops oldest lines when full).
Apps that insist on writing files: --read-only plus tmpfs mounts.

## Stats
docker container stats [name]      live stream, top-style; all
                                   containers when unnamed
  --no-stream                      single snapshot
Columns: CPU% (100% = one core), mem usage/limit, net and block I/O,
PIDs. Mem-vs-limit exposes OOM-kill loops; PIDs exposes unreaped
children.
Richer form, one endpoint per container, streams until closed:
  curl --no-buffer --unix-socket /var/run/docker.sock \
    http://docker/containers/<name>/stats | head -n 1 | jq

## Health checks
HEALTHCHECK CMD ["cmd"] in the Dockerfile: daemon runs it in the
container; exit 0 healthy, anything else unhealthy. Status appears in
container ls next to Up: (health: starting) -> (healthy)/(unhealthy).
Query: docker container inspect \
  --format='{{.State.Health.Status}}' <name>
Tuning: --health-interval, --health-retries, --health-start-period,
--no-healthcheck.
The daemon takes NO action on unhealthy: acting is the scheduler's
job. Compose consumes it via depends_on condition service_healthy,
which is the INSaFLU shape: web waits for the db probe. Docker
forwards traffic to ports while the process is still starting.

## Events
docker system events        blocks and streams the daemon lifecycle
                            feed; run in one terminal, act in another
Lifecycle: create, attach, network connect, start, die (with
exitCode), network disconnect, destroy.
--since / --until bound the window; recent events are cached, so a
crash remains visible after the fact.
Watch for: container oom; exec_create / exec_start / exec_die
(someone entered a container: possible security incident).
Raw API: curl --no-buffer --unix-socket /var/run/docker.sock \
  http://docker/events

## cAdvisor (deferred to today)
Google's per-container resource monitor, run as a container itself:
web UI on 8080, /metrics endpoint in Prometheus format (the standard
way Prometheus scrapes a Docker host). Needs ro bind mounts of /,
/var/run, /sys, /var/lib/docker, /dev/disk plus --privileged.
docker stats with history and graphs, exported for storage elsewhere.

## Prometheus daemon metrics
daemon.json: { "metrics-addr": "0.0.0.0:9323" }, restart dockerd,
curl http://host:9323/metrics. Monitors dockerd ITSELF, not
containers (cAdvisor's job). Book marks it experimental: stale, plain
metrics-addr has been stable for years. Do not expose 9323 publicly.
Rest of the stack parked in item 12.

## Odds
docker container cp         copy files in and out
docker image save / import  image to and from tarball
Everything the CLI does is the HTTP API underneath; the socket is
root-equivalent, so endpoint access is the security boundary, not
command output.

# Docker cheatsheet: chapter 7, debugging containers

## The premise
Container processes are ordinary host processes: shared kernel, host
sees everything. Debugging mostly happens FROM THE HOST with standard
tools; exec and nsenter are the fallback, not the front door.

## Process output
docker container top <name>     host-side ps of the container's
                                processes, from anywhere
UID display trap: top and host ps resolve UIDs against the HOST's
/etc/passwd. The container's uid 101 may print as uuidd, systemd+,
lp, or bare 101 depending on what the host has at that number. Paths
in ps output are the container's view, not the host's.
Mitigation the book suggests: dedicate one nonzero UID (e.g. 5000,
user "container") on hosts AND in base images, run everything -u
5000: readable ps, no root processes.

ps axlfww    BSD forest of everything: containers hang under
             containerd-shim-runc-v2, one shim per container.
             dockerd is NOT their parent (live-restore fact).
             a=all users, x=no-tty too, l=long, f=forest,
             ww=never truncate
ps -ejH      SysV tree, uglier
pstree `pidof dockerd`      collapsed map: docker-proxy children,
                            {threads} as N*[...]
pstree -p <shim-pid>        one container's full tree with PIDs
Alpine/BusyBox ps is crippled; full distro on daemon hosts.

## Process inspection
strace -p <hostpid>, lsof -p <hostpid>, gdb: all work from the host
as root against container processes. lsof paths are container-view.
Debug sidecar without touching the target image:
  docker container run -ti --rm --cap-add=SYS_PTRACE \
    --pid=container:<name> spkane/train-os bash
Joins the TARGET's PID namespace: its ps shows the target's
processes, strace -p 1 traces the target's main process. Tools come
from the debug image, not the stripped target.

## Controlling processes
kill from the host works on any container process. Killing a
non-PID-1 process does NOT stop the container: it leaves it in a
state no scheduler or developer expects. Rule: replace the whole
container instead of surgery inside it. docker container ls should
be trustable as "the app is whole".
Signals beyond TERM/KILL: docker container kill -s USR1 <name>
(nginx reopens logs on USR1, etc.).

## PID 1 duties
PID 1 in a container inherits init's duties: adopt orphans, reap
zombies, and it ignores SIGTERM without a handler. A forking app
does none of it: zombies accumulate (Jenkins agents the classic).
Fixes: docker run --init (docker-init = tini as PID 1; CMD passed
through, ENTRYPOINT REPLACED), entrypoint ending in exec app, or a
real supervisor (s6/runit/supervisord) for genuinely multi-process.
Verify: docker container exec <n> cat /proc/1/comm -> docker-init
Only needed for multi-parent or signal-deaf processes; tini is small
enough to default in production.

## Network inspection
docker network ls               bridge / host / none + compose extras
docker network inspect bridge   containers on it, their IPs, and
                                docker0 host binding
Containers have their own stack: they do NOT appear in host netstat
by address. The mapped port does:
netstat -an     port bound on 0.0.0.0
netstat -anp    bound process is docker-proxy: one per published
                port per family (v4+v6 = two). NO clue which
                container: docker container ls ties port to name.
Host networking mode: no proxy, process binds directly, shows
normally in netstat. tcpdump etc. work; remember the proxy sits
between host interface and container.
Default bridge until compose/scheduler says otherwise; NAME your
containers: name and ID are the only join key between network
inspect and container ls.

## Image history
docker image history <image>    layers with sizes and the commands
                                that built them, newest on top
Answers "why is this image huge". <missing> under IMAGE is normal
for pulled images (layer IDs unknown locally, only the top has an
ID). --no-trunc for full commands; pipe to less -S.

## Container directory on disk
/var/lib/docker/containers/<longid>/ on the daemon host:
  <id>-json.log     the docker logs backing store (json-file driver)
  config.v2.json    what inspect reads
  hostconfig.json   network/runtime config
  hostname, hosts, resolv.conf    the files bind-mounted into the
                                  container (chapter 5)
Readable even when the daemon is dead or the container unenterable.
NEVER edit: Docker expects these to reflect reality.

## Filesystem inspection
docker container diff <name>    what changed vs the image:
                                A added, C changed
Finds stray writes (logs, caches, .pid files): ammunition for the
--read-only=true + tmpfs + external-syslog conclusion. Deeper look:
export, exec, or nsenter.

## Author errata this chapter
p186: the long-ID listing and the container ls output are from
different sessions (no c58bfeffb9e6 in the list). Technique fine,
data mismatched.

## Chapter 8: Docker Compose

### What Compose replaces

The book opens with `scripts/shell_deploy.sh`: forty lines of `docker container run -d`
with `|| true` on every teardown line (shrugging at failure, per line), global `export`
blocks, and a `sleep 5` standing in for dependency ordering. Compose is the same stack
as one declarative YAML file.

### File anatomy

```yaml
version: '3'          # DEPRECATED, see note below
services:             # what to launch
networks:             # named networks
volumes:              # named volumes
```

```
2026-08-13: version: is deprecated. Compose Spec is versionless, features
negotiated by what the binary supports. Compose v2 ignores this key and warns.
No replacement key. name: (project name) is unrelated.
```

Compose v1 was Python, invoked as `docker-compose`. v2 is Go, a CLI plug-in,
invoked as `docker compose`. Check with `docker compose version`.

### Service keys seen in this chapter

| key | meaning |
| --- | --- |
| `build.context` | path to build dir, relative to the compose file. Presence means Compose can build it |
| `image` | tag to apply to the build, or to pull if no `build:` |
| `platform` | force arch, for example `linux/amd64`. Runs under QEMU/Rosetta elsewhere |
| `restart` | `unless-stopped` is the normal choice |
| `environment` | env vars passed into the container |
| `volumes` | `name:/path` (named volume) or `../host/path:/path` (bind) |
| `networks` | which named networks to attach |
| `ports` | `host:container`, published to the host |
| `expose` | port visible to other containers on the network, NOT to the host |
| `depends_on` | start ordering |
| `labels` | metadata, here consumed by traefik |
| `healthcheck` | see HEALTHCHECK in the Dockerfile |

### depends_on and health

```yaml
depends_on:
  mongodb:
    condition: service_healthy
```

Bare list form waits only for *running*. The `condition: service_healthy` form waits
for the image's `HEALTHCHECK` to pass. Startup only: Docker reports later unhealth,
it does not act on it. A container that exits gets restarted per `restart:`, that is all.

### Service discovery

Containers on the same Compose network resolve each other by service name.
`mongodb://mongodb:27017/...`, never an IP, never an FQDN. Names survive rearrangement
and document the dependency in the file.

### Project name

Container and network names are prefixed by the project name, which defaults to the
directory containing the compose file. Running in `compose/` yields
`compose-mongodb-1`, `compose_botnet`. Override with the top-level `name:` key.

### Volume prepopulation trick

Compose can create empty volumes, not populated ones. To ship a preinitialized
database:

```
docker volume create mongodb-rocketchat

docker run --rm \
    -v mongodb-rocketchat:/bitnami/mongodb \
    -v ${PWD}:/backup busybox \
    tar -xzvf /backup/mongodb-rocketchat.tgz -C /bitnami/mongodb
```

Ephemeral busybox, two mounts (target volume plus the backup dir), untar, exit.
Volume survives, container does not. Pair with:

```yaml
volumes:
  mongodb-rocketchat:
    external: true
```

`external: true` means Compose mounts and unmounts it but does not own its lifecycle:
`docker compose down` will not delete it.

Split-host note: `${PWD}` and all `-v` paths resolve DAEMON-side. Running this from
molly against the dockervm context untars a path on docker.marsel.is.

### Commands

```
docker compose config                   # lint + print the fully resolved file
docker compose build                    # build services with build:, skip image-only
docker compose up -d                    # create network, volumes, containers
docker compose logs                     # all services, color coded, time interlaced
docker compose logs <service>           # one service
docker compose top                      # processes per container
docker compose exec <service> <cmd>     # -it implied, service name not container name
docker compose stop|start <service>
docker compose pause|unpause
docker compose down                     # remove containers and network
docker compose -f <file> <cmd>          # pick a non-default compose file
```

`config` failure looks like: `services.mongodb Additional property builder is not allowed`.

`logs` and `exec` are the two troubleshooting commands. If the image will not build or
the container will not start at all, fall back to plain `docker` commands.

```
docker compose exec <service> <cmd>: exec into the container backing that SERVICE
(project's <service>-1), resolved from the compose file in the current dir. -it
implied, service names not container names. "I have no name!" = process uid
(bitnami: 1001) has no /etc/passwd entry in the image. UID lesson, container-side.
```

```
Compose "validation for free", concretely:
1. Schema: YAML checked against spec pre-daemon: unknown keys, wrong types, bad
   port strings refused with file+line. Standalone: docker compose config
2. References: undefined volumes/networks/depends_on targets caught before start
3. Ordering: depends_on sequencing, consistent naming, idempotent up
NOT validated: anything inside containers (env values), image existence,
cross-field sanity.
```

### Variable interpolation

Borrowed from shell. Three forms:

```yaml
${VAR}                        # plain
${VAR:-default}               # default if unset OR empty
${VAR-default}                # default if unset only (empty string is a valid value)
${VAR:?error message}         # mandatory, fail with this message
```

Mandatory failure:

```
required variable HUBOT_ROCKETCHAT_PASSWORD is missing a value:
  HUBOT_ROCKETCHAT_PASSWORD must be set!
```

Verify resolution without starting anything:

```
docker compose -f docker-compose-env.yaml config | grep ROCKETCHAT_PASSWORD
VAR=value docker compose -f docker-compose-env.yaml config | grep ROCKETCHAT_PASSWORD
```

### .env

Read automatically from the directory containing the compose file. Key/value pairs,
host-side, consumed by Compose itself for interpolation.

Traps:
- NOT a shell script. Do not quote values. `PW="foo"` yields literal `"foo"`.
- `.gitignore` it. It exists to hold the thing you must not commit.
- Ambient pickup: it is read because it is *there*, no flag, no reference in the YAML.
  A stale `.env` in the directory silently changes what you deploy.
- Project `.env` (host-side, interpolation) is not `env_file:` (container-side, injects
  vars into the container). Different mechanisms, similar names.

Precedence, lowest to highest:

```
1. defaults in docker-compose.yaml
2. .env file
3. environment variables set in the shell
```

### Secrets

```
Secrets: env vars are the WRONG channel: visible in docker inspect, inherited by
children, leaked to logs/crash dumps. ${VAR:-default} adds the repo-default sin on
top. Right channel: compose secrets: -> files at /run/secrets/<name>, never in env,
never in inspect. App reads a file, not os.environ. Jenkins credential-binding
injects secrets as env: the cautionary example, not the model. Book covers secrets
properly in ch11.
```

The book also notes the command-line problem it creates: `HUBOT_ROCKETCHAT_PASSWORD=x
docker compose up` puts the password in the process list.

### Override files

Not covered by the book beyond one sentence, and the single most useful Compose
feature for consuming someone else's stack.

`docker-compose.override.yml` in the same directory is read automatically and merged
on top of `docker-compose.yaml`. Merge is per-key: scalars replace, most lists append,
maps merge. No flag needed. Explicit form:

```
docker compose -f docker-compose.yaml -f docker-compose.override.yml up -d
```

This is THE tool for modifying INSaFLU without forking their compose file: their file
stays pristine and updatable, our changes live in a separate file we own.

### Production caution

Host bind mounts for state are a development convenience. In production the container
lands on whichever node has room and loses the files. Network storage or k8s PVs.

### Staleness

- `version:` deprecated, see note above.
- `docker-compose` (hyphen, Python v1) is EOL. Everything is `docker compose`.
- Override files are documented Compose Spec, not an obscure extra.

## Chapter 9: The Path to Production Containers

Prose chapter. One command in the whole thing. Read for the concern stack and
the vocabulary, not for technique.

### The concern stack (figure 9-1)

Bottom to top. Docker owns the lower half, the "platform" owns the upper half.

| Concern | Owner | Book claims it replaces |
| --- | --- | --- |
| Configuration, networking, resource limits, job control | Docker | VMs, Puppet/Chef, init, deploy scripts |
| Delivery, packaging | Docker | FAT jars, tarballs, git clone, scp, rsync |
| Logging | boundary | syslog, rsyslog, logfiles |
| Service discovery, scheduling, monitoring | platform | static load balancers, orchestration, Nagios/Sensu, staff on call |
| Application | you | |

```
Figure 9-1 "Replaces" column is overstated, in three places:

Static load balancers: what dies is the hand-edited BACKEND LIST, not the
load balancer. Under a scheduler the list is generated from the service
registry. The LB becomes a k8s Service or haproxy templated from
etcd/Consul.

Nagios/Sensu: what the platform replaces is liveness-check plus restart
(HEALTHCHECK, liveness probe, supervisor). Nagios also did metric
thresholds, alert routing, escalation, dependency suppression. None of that
is in the platform. You replace Nagios with Prometheus + Alertmanager, not
with Kubernetes. The book conflates SELF-HEALING with MONITORING.

Staff on call: retracted by the text on p221, "a human will still need to
be the final line of defense". Restart fixes crashes. It does not fix bad
config, full disks, dependency outages, or corruption, and restarting into
those produces crashloops that page you anyway.
```

### Where-scheduling vs when-scheduling

```
"Scheduling" here means WHERE-scheduling only: kube-scheduler picks a node
per pending pod (filter by resources/taints/affinity, score, bind).
Placement, not timing.

WHEN-scheduling is the other half: a queue, walltime, ordering by
priority/fairshare, backfill. Slurm does both. Borg does both. Kubernetes
dropped the queue: a pod is placeable now or Pending until something
changes. No walltime, no completion time, so no backfill and no fairness
across users.
```

### Networking rules for a portable container

1. Let the platform map ports and tell the app what they are, usually via an
   env var.
2. Avoid protocols that negotiate random return ports: FTP active mode, RTSP.
   RTSP is the camera/video streaming control channel, TCP 554 for
   PLAY/PAUSE with video returning over separately negotiated UDP ports.
   Same NAT breakage as FTP.
3. Use the DNS the runtime gives the container.

### Configuration

```
Booooooo. 30 years of trying to make apps have individual conf files.
```

The book's position: env vars are Docker's native mechanism and work
everywhere. Kubernetes makes files easy (ConfigMaps) and the authors
explicitly recommend against it, calling file-based config a crutch that hurts
observability. Reasoning deferred to chapter 13, twelve-factor.

Note that this is the opposite advice from chapter 8's secrets section, where
env is the wrong channel and files under /run/secrets are right. Config and
secrets are different problems: config wants visibility, secrets want the
opposite.

### Service discovery

The mechanism by which an app finds the address of a service it needs. That is
the whole definition.

"Dynamic" is the container property that breaks the old answers: the container
lands on whichever node has room, on a random published port, dies, comes back
elsewhere. The address is not knowable at config-write time.

The book's list, grouped:

| Group | Mechanisms | Knows if the endpoint is alive |
| --- | --- | --- |
| DNS-based | round-robin DNS, SRV records, dynamic DNS, mDNS/Bonjour | no |
| Consistent store you query | ZooKeeper, Consul, etcd | yes |
| Address indirection | LB with well-known address, overlay with well-known address | via health check on the LB |

```
DNS was always this mechanism: SRV records did exactly this in 2000. What
changed is not the query, it is the WRITE PATH: who updates the record when
a container moves, and how fast. Old DNS assumed a human editing a zone
file and TTLs in hours. Cluster DNS is the same protocol with the registry
as authoritative source, updated in seconds, and k8s dodges TTL entirely by
putting a stable virtual IP in front so the record never has to change.

Speed of update plus who does the updating. The protocol was never the
problem.
```

Compose's service-name DNS from chapter 8 is the simplest form of this: `dockerd`
supplies the DNS, `mongodb://mongodb:27017` resolves. It works within one host's
Compose network. Across a cluster the platform must provide it.

Ingress into a containerized system from a traditional one is the harder
direction and the one to solve first. Book's examples: k8s Ingress controllers
(Traefik, Contour), Linkerd, Envoy standalone or under Istio.

### The one command

Test the exact image you will ship, overriding CMD at runtime:

```
docker container run -e ENVIRONMENT=testing -e API_KEY=12345 \
    -it awesome_app:version1 /opt/awesome_app/test.sh
```

- `docker container run` exits with the exit status of the command it ran. That
  is the pass/fail signal. Do not parse output if the exit code works.
- Pass a precise tag, never `latest`: another build can move `latest` between
  the trigger and the run.
- `--entrypoint` if ENTRYPOINT and not CMD needs overriding.
- Concessions for testing must be external switches (env vars, args), never a
  different build.

### CI workflow (figure 9-2)

trigger -> build image -> tag with version/commit hash -> run container with
the test command -> capture exit status -> mark pass/fail -> `docker image tag`
and `docker image push` to the registry on pass.

The registry is the interchange point between build and deploy.

Note the split-host pattern the book uses: the test worker has the `docker` CLI
but no daemon, and builds against a remote `dockerd`. Same shape as
molly -> docker.marsel.is, and the same `${PWD}`/`-v` daemon-side resolution
trap applies.

### Staleness

- Mesos and Aurora are dead: Apache Attic 2021 and 2020 respectively. D2iQ
  wound down. Twitter, the flagship user, migrated to Kubernetes.
- Swarm mode still ships but is legacy. The book already hedges this.
- Consul is alive but compressed into mixed VM-plus-container fleets, since k8s
  ships its own DNS and health checks.
- "Kubernetes is not the only option" was a weaker hedge by 2026 than when
  written. Nomad and ECS are alive; nothing else general-purpose is.

### Terms introduced

- **Borg**: Google's internal cluster manager, running since ~2004, EuroSys
  2015 paper. Kubernetes is its public rewrite (Omega was the intermediate
  attempt). Carried over: pods (Borg allocs), labels instead of hostnames,
  declarative specs, one agent per node. NOT carried over: the queue,
  admission control, priority tiers with preemption, and reclaiming the gap
  between reserved and actual usage.
- **Consul**: HashiCorp. Agent per node registers local services with health
  checks, Raft server cluster holds the catalog, clients query by DNS or HTTP.
  Failing checks drop a node from the answer. Also KV and, later, a mesh.
  Difference from etcd: etcd is a generic consistent store you build discovery
  on, Consul is discovery as the product.
- **etcd**: sorted key space, put/get/delete/watch, leases for TTL,
  compare-and-swap. API is an afternoon. Operating it is the work: Raft quorum
  means odd member counts, the store must be compacted and defragmented or it
  wedges at the 2GB default, lost quorum is restore-from-snapshot.
- **CNI**: Container Network Interface. A plugin contract, not a network.
  Kubelet creates the pod netns then shells out to a binary that assigns an IP
  and plumbs the interface. k8s states the requirement (every pod gets a
  routable IP, any pod reaches any other without NAT) and refuses to implement
  it, because four right answers exist: overlay (VXLAN/Geneve, no cooperation
  from the network, MTU pain), native routing (BGP/Calico, fast and
  observable, needs the network team), cloud VPC IPs (ideal until the
  per-instance IP limit), eBPF datapath (Cilium, replaces kube-proxy, needs
  kernel versions). No default is right everywhere and picking one kills the
  others commercially. Same inter-vendor seam shape as 1985 LDAP.
- **Blue-green deploy**: run the new generation alongside the old, migrate
  traffic across, keep the old until confident.
- **Tetris metaphor**: Kelsey Hightower's, for the scheduler placing services
  on servers for best fit on the fly.


