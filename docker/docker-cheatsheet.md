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
