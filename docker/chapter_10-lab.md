# Chapter 10 lab: Swarm mode and Kubernetes

## Contents

1. Hosts
2. Rolling the swarm VMs
3. ssh config and Docker contexts on molly
4. Swarm init and join
    1. Promote and demote
5. Hardening
    1. Firewall the swarm ports (host OS, all three)
    2. Autolock (manager)
    3. Rotate join tokens (manager)
    4. Encrypted overlay (manager)
    5. Rotate the CA (manager)
    6. Verify
6. Ingress subnet collision
7. Services
8. Stacks
9. Tear down
10. Kubernetes installation checklist
11. Kubernetes on kubeadm: the redo
    1. Purge minikube
    2. kubeadm init
    3. kubeconfig, on the node and then on molly
    4. CNI: flannel
    5. Untaint the control plane
    6. hello-minikube without minikube
    7. lazyraster and the storage deadlock
    8. Observations
    9. Tear down

Every section that does something has the same shape: what it is, why we
do it, the commands, what we observed.

---

## 1. Hosts

We have three Docker hosts:

| host | ip | role | ssh alias |
| --- | --- | --- | --- |
| docker.marsel.is | 10.0.0.7 | manager | d.m |
| swarm1.marsel.is | 10.0.0.9 | worker | sw1.m |
| swarm2.marsel.is | 10.0.0.10 | worker | sw2.m |

All three run Debian 13 and Docker 29.7.x. Managers run workloads by
default as well.

You should use odd manager counts, because Raft quorum is a strict
majority: three managers tolerate one loss, four also tolerate only one and
add a 2-2 split. Our lab has one manager, which brings no fault tolerance.

## 2. Rolling the swarm VMs

Two throwaway Debian 13 VMs on 3jane. The preseeds are derived from
docker.marsel.is with docker-ce installed in late_command; docker.marsel.is
itself was left bare on purpose so the install could be done by hand once.
The hostname is set by writing /etc/hostname in late_command, because
in-target is a chroot with no systemd and hostnamectl fails there. The
partman recipe needs a 20GB disk minimum.

On 3jane, swarm1:

```
/usr/bin/time /usr/bin/virt-install --name swarm1.marsel.is --memory 1024 --vcpus 1 --disk pool=default,size=20,format=qcow2 --location /var/lib/libvirt/iso/debian-13.4.0-amd64-netinst.iso --os-variant debian13 --boot uefi --network bridge=br-eno2,model=e1000 --graphics none --console pty,target_type=serial --initrd-inject /home/gmarselis/src/pret-a-booter/swarm1.marsel.is.preseed.cfg --extra-args="console=ttyS0,115200n8 auto=true priority=critical preseed/file=/swarm1.marsel.is.preseed.cfg systemd.ssh_auto=no" --wait=-1
```

swarm2:

```
/usr/bin/time /usr/bin/virt-install --name swarm2.marsel.is --memory 1024 --vcpus 1 --disk pool=default,size=20,format=qcow2 --location /var/lib/libvirt/iso/debian-13.4.0-amd64-netinst.iso --os-variant debian13 --boot uefi --network bridge=br-eno2,model=e1000 --graphics none --console pty,target_type=serial --initrd-inject /home/gmarselis/src/pret-a-booter/swarm2.marsel.is.preseed.cfg --extra-args="console=ttyS0,115200n8 auto=true priority=critical preseed/file=/swarm2.marsel.is.preseed.cfg systemd.ssh_auto=no" --wait=-1
```

## 3. ssh config and Docker contexts on molly

A Docker context is a named daemon endpoint. One docker binary on molly
drives all three daemons; `docker -H ssh://d.m` is the same thing without
naming it. A bare `-H d.m` means tcp://d.m:2375, the unencrypted socket,
which is not open on any of our hosts.

ssh aliases:

```
printf '\nHost sw1.m swarm1.marsel.is\n    Hostname 10.0.0.9\n    User gmarselis\n    IdentityFile /home/gmarselis/.ssh/id_ed25519.molly\n\nHost sw2.m swarm2.marsel.is\n    Hostname 10.0.0.10\n    User gmarselis\n    IdentityFile /home/gmarselis/.ssh/id_ed25519.molly\n' >> ~/.ssh/config
```

Accept the new host keys once:

```
ssh -o StrictHostKeyChecking=accept-new sw1.m
ssh -o StrictHostKeyChecking=accept-new sw2.m
```

Contexts:

```
docker context create sw1 --docker host=ssh://sw1.m
docker context create sw2 --docker host=ssh://sw2.m
docker --context sw1 version --format '{{.Server.Version}}'
docker --context sw2 version --format '{{.Server.Version}}'
```

Observed: 29.7.2 on both, straight from preseed.

## 4. Swarm init and join

There is a worker join token and a manager join token. The join command is
identical; which token you pass decides whether the node joins as a worker
or a manager. `join-token` only works on a manager, since workers hold no
cluster state (the book says "any active node", which is wrong).

From molly, init on the manager and capture the worker token:

```
docker -H ssh://d.m swarm init --advertise-addr 10.0.0.7
TOKEN=$(docker -H ssh://d.m swarm join-token -q worker)
```

Join the workers:

```
docker --context sw1 swarm join --token $TOKEN 10.0.0.7:2377
docker --context sw2 swarm join --token $TOKEN 10.0.0.7:2377
docker -H ssh://d.m node ls
```

Observed: three nodes Ready, docker.marsel.is Leader. The `*` in `node ls`
marks the node the CLI is talking to.

### 4.1 Promote and demote

A joined worker can be turned into a manager in place with `docker node
promote`: it receives a manager certificate, joins the Raft group and starts
replicating cluster state, with no leave and rejoin. `docker node demote`
reverses it.

Why: the book says adding managers is as easy as adding workers, and that a
swarm should run three or more. We have one. Promoting a worker in place is
how you get there, and it is worth doing once on a lab cluster so the first
time is not on a production one.

```
docker -H ssh://d.m node promote swarm1.marsel.is
docker -H ssh://d.m node ls
docker -H ssh://d.m node demote swarm1.marsel.is
docker -H ssh://d.m node ls
```

Observed: swarm1 shows Reachable under MANAGER STATUS after promote, blank
after demote. Two managers is an even count and briefly the wrong shape for
production: quorum is a strict majority, so with two, losing either one
loses quorum and the cluster stops accepting changes. Same tolerance as one
manager, twice the exposure. Fine for the duration of the exercise.

## 5. Hardening

The book says: "There are steps that you must take to secure a Docker Swarm
mode cluster, which we are not covering here." Here they are. The firewall
step is host OS configuration and runs on all three Debian machines. The
rest change swarm cluster state and run once, against the manager.

### 5.1 Firewall the swarm ports (host OS, all three)

This runs on the three VMs themselves, docker.marsel.is, swarm1.marsel.is
and swarm2.marsel.is, as host OS firewall rules. Nothing here touches a
container or an image; it is the machines the swarm runs on.

Why: 2377/tcp is the join and management API; a token holder who reaches it
joins, and a joined manager owns the cluster. 7946 tcp+udp is gossip, node
membership, spoofable to poison the member list. 4789/udp is the VXLAN
overlay, no authentication, any host reaching it injects frames into every
overlay network. Swarm trusts the network at these ports, and the firewall
is what makes that trust true. On the lab bridge only our hosts can reach
them, so this is practice, not protection.

```
for h in d.m sw1.m sw2.m; do ssh $h "sudo nft add table inet swarm; sudo nft add chain inet swarm input '{ type filter hook input priority 0; policy accept; }'; sudo nft add rule inet swarm input ip saddr 10.0.0.0/24 tcp dport '{ 2377, 7946 }' accept; sudo nft add rule inet swarm input ip saddr 10.0.0.0/24 udp dport '{ 7946, 4789 }' accept; sudo nft add rule inet swarm input tcp dport '{ 2377, 7946 }' drop; sudo nft add rule inet swarm input udp dport '{ 7946, 4789 }' drop; sudo sh -c 'nft list table inet swarm > /etc/nftables.conf'; sudo systemctl enable --now nftables"; done
```

We persist only our own table, inet swarm, and not the full ruleset. `nft
list ruleset` would also dump the ip nat, ip filter and ip6 nat tables that
dockerd creates through iptables-nft (the "managed by iptables-nft, do not
touch" warnings). If those are saved, nftables.service restores stale
Docker rules at boot before dockerd starts and rewrites them. Usually
harmless, sometimes duplicate chain errors. Docker owns its tables and
regenerates them on every start.

Observed: table created and persisted on all three, iptables-nft warnings
printed as expected.

### 5.2 Autolock (manager)

Autolock is encryption at rest for the manager's Raft store, the directory
under /var/lib/docker/swarm where every manager keeps the cluster state.
That store holds the swarm CA private key, every node's TLS key and any
docker secrets. Without autolock all of that sits on disk in cleartext, so
a copied disk or a stolen VM image yields the whole cluster.

Why: with autolock on, the store is encrypted with a key that exists only
in the running dockerd's memory. When a manager's dockerd restarts it comes
up locked: it will not read its own state, and so cannot rejoin the Raft
group or serve as a manager, until someone runs `docker swarm unlock` and
provides the SWMKEY. The trade is that every manager restart needs a human
or a vault, which is the point.

```
docker -H ssh://d.m swarm update --autolock=true
docker -H ssh://d.m swarm unlock-key         # show it again
docker -H ssh://d.m swarm unlock             # after every manager dockerd restart
```

Observed: SWMKEY printed, autolock true in `docker info`.

Production reminder: never store the unlock key on disk on the nodes. It
goes in a password manager or vault, never in docker secrets: secrets live
inside the locked Raft store, so you cannot read the key you need to unlock
it. Lab exception: this repo, lab password rules apply.

### 5.3 Rotate join tokens (manager)

Every `swarm init` generates a new CA and new random secrets, so tokens
differ from cluster to cluster. Within one cluster, though, the join token
is stored state and never changes by itself.

Why: anyone who ever saw the token (this chat, a shell history, a paste)
can add a node forever. Rotating after initial join invalidates every copy
in the wild; nodes already joined are unaffected because membership is held
by certificate, not token. Rotate the manager token first, it is the one
that hands out the cluster.

```
docker -H ssh://d.m swarm join-token --rotate manager
docker -H ssh://d.m swarm join-token --rotate worker
```

Observed: only the trailing secret segment changed. The middle segment is
the CA hash and changes in 5.5.

Production reminder: join tokens do not live on disk on the nodes. A vault
or docker secrets for automation are fine, since they are needed only at
join.

### 5.4 Encrypted overlay (manager)

Overlay traffic is VXLAN (Ethernet frames tunneled inside UDP packets
between hosts, port 4789) and travels in cleartext by default.

Why: anyone on the fabric between nodes reads inter-container traffic.
`--opt encrypted` wraps it in IPsec ESP with keys the managers rotate. Cost
is CPU per packet, and it only matters when the network between hosts is
not yours. On the lab bridge it is a demonstration.

```
docker -H ssh://d.m network create --driver overlay --opt encrypted secure-net
```

Observed: network id returned, nothing else to see until a service uses it.

The book creates an unencrypted `default-net` on p236 and uses that name in
every `service create` that follows. We use `secure-net` in its place
throughout.

### 5.5 Rotate the CA (manager)

Swarm runs its own certificate authority. `swarm init` creates a root CA
and issues every node a certificate signed by it, and all manager and
worker traffic is mutual TLS against that root. An external CA can be
plugged in on init or update, but only the CFSSL signing API is supported
and almost nobody does this:

```
docker swarm init --advertise-addr 10.0.0.7 --external-ca protocol=cfssl,url=https://ca.example.com:8888
docker swarm update --external-ca protocol=cfssl,url=https://ca.example.com:8888
```

Why: the CA's private key lives in the Raft store on every manager.
Rotating issues a new root, reissues every node's certificate against it
and stops trusting the old ones. Rotation is advised if a manager disk was
ever copied before autolock was on, or if the CA is simply old. It also
changes the middle segment of the join tokens, since that segment is the CA
hash.

Rotating is not strictly required. It is good practice to do it once before
a cluster goes to production, and worth doing once in the lab so you have
already seen that it does not knock joined workers off.

```
docker -H ssh://d.m swarm ca --rotate
```

Observed: 3/3 nodes rotated, new root ECDSA P-256 valid to 2046, no worker
fell off.

Rotation risk: a worker unreachable during `ca --rotate` cannot fetch its
new certificate, and once managers drop the old CA it is out. Its old
certificate is dead, the node is not: `docker swarm leave --force` on the
worker, then a fresh join with the current token.

### 5.6 Verify

```
docker -H ssh://d.m info --format '{{.Swarm.Cluster.Spec.EncryptionConfig.AutoLockManagers}}'
docker -H ssh://d.m swarm join-token worker
docker -H ssh://d.m node ls
for h in d.m sw1.m sw2.m; do ssh $h 'sudo nft list table inet swarm'; done
```

Observed: true; token CA-hash segment changed from 35vl1lx2... to
3czof4lc...; three nodes Ready; inet swarm table present on all three
hosts.

## 6. Ingress subnet collision

Docker's default ingress overlay network is 10.0.0.0/24, and so is our lab
LAN. A request from molly (10.0.0.20) to a published port is DNAT'd into
the ingress sandbox, which has its own interface on 10.0.0.0/24; the
sandbox routes the reply out its overlay interface, thinking molly is a
peer on the overlay, and the reply never comes back. From the host itself
it works because the source is not in the colliding range. Network segment
collision, nothing to do with the firewall or the app.

Symptom: `service ps` shows tasks Running, curl from the node itself
answers, curl from anywhere else hangs; tcpdump on the node shows the SYN
going into docker_gwbridge and no reply.

Fix: ingress can only be replaced when nothing publishes through it.
Recreated encrypted as well, so the mesh's node-to-node hop gets the same
IPsec as secure-net.

```
docker -H ssh://d.m service rm quantum
docker -H ssh://d.m network rm ingress
docker -H ssh://d.m network create --driver overlay --ingress --opt encrypted --subnet 10.255.0.0/16 ingress
docker -H ssh://d.m service create --detach=true --name quantum --replicas 2 --publish published=80,target=8080 --network secure-net spkane/quantum-game:latest
```

Debug commands that got there:

```
docker -H ssh://d.m service ps quantum
docker --context sw1 exec $(docker --context sw1 ps -q | head -1) wget -qO- http://127.0.0.1:8080/ | head -3
ssh sw1.m 'sudo iptables -t nat -L DOCKER-INGRESS -n'
ssh sw1.m 'curl -sI http://127.0.0.1/ | head -1; curl -sI http://10.0.0.9/ | head -1'
ssh sw1.m 'sudo timeout 5 tcpdump -ni any port 80 -c 6' & sleep 1; curl -sI -m 3 http://10.0.0.9/ | head -1; wait
ssh sw1.m 'sudo nsenter --net=/var/run/docker/netns/ingress_sbox ip addr | grep inet'
```

## 7. Services

The book's `-H 172.17.4.1` is the tcp:2375 form; ours is `-H ssh://d.m`
throughout. Network `default-net` becomes `secure-net`.

Create, p237:

```
docker -H ssh://d.m service create --detach=true --name quantum --replicas 2 --publish published=80,target=8080 --network secure-net spkane/quantum-game:latest
```

The manager stores the service spec in the Raft store, the scheduler picks
nodes, each node's dockerd pulls the image and starts a task. `--detach=true`
returns the service id immediately.

List, p238:

```
docker -H ssh://d.m service ls
```

MODE replicated, REPLICAS 2/2 (running/desired), PORTS `*:80->8080/tcp` means
published on every node via the routing mesh. Typesetting bug in the book:
`+service ls+` is unrendered AsciiDoc that leaked into print.

Update behaviour, p239. `service inspect --pretty` shows UpdateConfig and
RollbackConfig. A service update replaces tasks one batch at a time; these
settings say how big the batch is, in what order a task is replaced, how
long to watch the new task, and what to do if it fails. Rollback has the
same knobs for the reverse direction.

| option | meaning |
| --- | --- |
| `--update-parallelism N` | tasks replaced per batch. With 2, two tasks are stopped and replaced together, monitored together, then the next two; capacity dips by 2 per batch under stop-first and a 15-replica service takes 8 batches instead of 15. Larger N is faster and riskier: a bad image takes out N tasks before the monitor period catches it. 1 is safest, 0 means all at once (outage) |
| `--update-order stop-first` | stop the old task, then start the new. N is the replica count you asked for, the capacity you sized the service to; for the duration of each swap you run one short of it, N-1. If N was already the minimum for your load, every update is an overload window; if you sized with headroom, N-1 is fine. That is the book's "run N+1 in production": one replica more than you need, so stop-first never drops below what you actually need. N+1 is one extra replica across the service, not one per node: if load needs 2, run 3, and the swap leaves you at 2. Where the extra lands is the scheduler's choice, and it can share a node with another replica. Our quantum at 2 replicas with load needing 1 is already N+1. Default |
| `--update-order start-first` | start the new task, wait for it, then stop the old; N+1 during the swap, never below N. Needs room for one extra task and an app that tolerates two versions side by side |
| `--update-delay` | pause between batches, e.g. 10s |
| `--update-monitor` | how long a new task is watched for failure before the next batch. Default 5s; too short and a slow-crashing image rolls out fully before anyone notices |
| `--update-max-failure-ratio` | fraction of failed tasks tolerated before the failure action fires. 0 means the first failure |
| `--update-failure-action pause` | stop rolling, leave the mix in place for a human. Default |
| `--update-failure-action continue` | keep going regardless |
| `--update-failure-action rollback` | revert to the previous spec using the RollbackConfig settings |
| `--rollback-parallelism N` | tasks rolled back at once |
| `--rollback-order stop-first` / `start-first` | same meaning as the update order, for the rollback direction |
| `--rollback-delay` | pause between rollback batches |
| `--rollback-monitor` | how long a rolled-back task is watched before the next batch |
| `--rollback-max-failure-ratio` | failures tolerated during rollback before the rollback failure action fires |
| `--rollback-failure-action pause` / `continue` | what to do if the rollback itself fails; there is no rollback-of-rollback |

Most useful in production:

`--update-order start-first`: the new task is up and in the balancer before
the old one is stopped, so at no point are you below N. Costs one task's
worth of CPU and memory extra during the swap, and the app must run two
versions side by side.

`--update-failure-action rollback`: a bad image undoes itself. Rollback has
the same mechanics as an update, in reverse and per RollbackConfig: tasks on
the bad image are replaced by tasks on the previous image, batch by batch. A
user with a request in flight on a task that gets stopped sees a connection
reset, exactly as during the update; everyone else is served by tasks still
in the pool. Under stop-first rollback that pool briefly has old, bad, and
mid-swap gaps; under start-first rollback the previous copy is up before the
bad one goes. Sessions held in memory on a killed task are gone either way,
which is why session state belongs outside the container.

`--update-monitor` long enough to see the app actually fail, 30s to a
minute for anything that talks to a database. `--update-delay` a few
seconds so a bad batch does not stampede. Set once at create; they stick to
the service.

The book's "N-1" is per batch, not per service: with parallelism 1 and 15
replicas you are at 14 during each swap, never at 0. During the roll the
routing mesh has old and new tasks in the pool at once and each request
lands on either; nothing pins a client to a version. The app must tolerate
two versions side by side, and database migrations under rolling updates
are the actual hard part.

Set on our service:

```
docker -H ssh://d.m service update --update-order start-first --update-failure-action rollback --update-monitor 30s --update-delay 5s quantum
docker -H ssh://d.m service inspect --pretty quantum | grep -A6 UpdateConfig
```

Scale, p238. Adds or removes tasks, never touches the running ones. On
scale-down the scheduler picks which to stop, newest first in practice,
keeping the spread across nodes even.

```
docker -H ssh://d.m service scale --detach=false quantum=4
docker -H ssh://d.m service ps quantum
```

Rolling update, p239:

```
docker -H ssh://d.m service update --update-delay 10s --update-failure-action rollback --update-monitor 5s --update-order start-first --update-parallelism 1 --detach=false --image spkane/quantum-game:latest-plus quantum
```

One task at a time: new task on latest-plus starts, joins the balancer, is
watched 5s, its old counterpart is stopped, wait 10s, next. Four swaps for
four replicas, capacity never below 4, users hit either version during the
roll. A failure inside the 5s window rolls the whole service back to latest.

The update pulls the image: the manager resolves the tag to a digest once,
each node pulls that digest when its task is scheduled. Under start-first
the pull completes before the old task stops, so slow pulls cost time, not
capacity.

Manual rollback, p240. Same rolling mechanics in reverse, per RollbackConfig.
Docker keeps exactly one previous spec, not a history; a second rollback
returns you to where you started.

```
docker -H ssh://d.m service rollback quantum
```

## 8. Stacks

`stack deploy` takes a Compose file and creates one swarm service per
Compose service, plus overlay networks and volumes, all prefixed with the
stack name. Same file format as chapter 8, but the `deploy:` block per
service now matters: replicas, placement constraints, update config,
resource limits. Compose ignores that block, swarm reads it.

The stack is only a label. `stack ps`, `stack services`, `stack rm` operate
on everything carrying it; underneath they are ordinary services. What it
buys you: one file, one command, one label for the whole application, and
re-running `stack deploy` with an edited file is a rolling update of
whatever changed. Compose for the cluster: you declare the set, the
where-scheduler places each piece, the mesh and the overlay make location
irrelevant for traffic. Storage is the one thing that still cares where.

Deploy, p241, from the repo's compose/ directory on molly. The file is read
client-side, so no split-host issue:

```
docker -H ssh://d.m stack deploy --compose-file docker-compose-stack.yaml rocketchat
docker -H ssh://d.m stack ps rocketchat
```

Observed: hubot and mongodb on docker.marsel.is, rocketchat and zmachine on
swarm1. mongodb landed where the prepopulated volume lives; named volumes
are per-node, so had it gone to a worker it would have started empty and
rocketchat would have no database. Check whether the file pins it:

```
grep -n -A3 "placement\|constraints\|volumes:" docker-compose-stack.yaml
```

List, p242. `stack ls` shows the label and its service count; `service ls`
shows the stack's services alongside quantum, prefixed `rocketchat_`, with
mongodb and zmachine unpublished (no PORTS) and hubot on 3001, rocketchat on
3000 via the mesh:

```
docker -H ssh://d.m stack ls
docker -H ssh://d.m service ls
```

Remove, p242. Services and the stack's network go, volumes stay, same rule
as `compose down`. `stack rm` returns as soon as the removal is requested;
tasks stop and the network is torn down asynchronously behind it. That is
why the book warns that redeploying immediately can error: wait a moment.

```
docker -H ssh://d.m stack rm rocketchat
```

Drain, p243. Evicts every task from a node and reschedules them elsewhere;
the node stays in the swarm but gets nothing new. Undo with `active`, but
tasks do not move back on their own; a forced update reschedules them.

```
docker -H ssh://d.m node update --availability drain swarm2.marsel.is
docker -H ssh://d.m node inspect --pretty swarm2.marsel.is
docker -H ssh://d.m node update --availability active swarm2.marsel.is
docker -H ssh://d.m service update --force quantum
docker -H ssh://d.m service ps -f "desired-state=running" quantum
```

Observed: after the forced update, four quantum tasks spread across all
three nodes, swarm2 included. `-f desired-state=running` hides the `\_`
task-history rows.

Side observation: with the setup wizard skipped, hubot crash-loops (exit 1
every 12s) because the Rocket.Chat user it needs does not exist. The
retained history rows under it are the Task History Retention Limit of 5
from `docker info`.

Swarm vs Kubernetes: same job (declare, schedule, route, roll). Kubernetes
does it with a general API and reconciliation loops instead of a fixed
command set, so everything is an object you can extend and every piece is
pluggable; that is where the fiddly comes from. Swarm is Kubernetes with
the choices made for you and the ceiling low.

## 9. Tear down

Workers leave first, then the manager, so no orphan state is left in the
Raft store:

```
docker --context sw1 swarm leave
docker --context sw2 swarm leave
docker -H ssh://d.m swarm leave --force
```

Destroy the VMs, on 3jane:

```
virsh destroy swarm1.marsel.is; virsh undefine swarm1.marsel.is --nvram --remove-all-storage
virsh destroy swarm2.marsel.is; virsh undefine swarm2.marsel.is --nvram --remove-all-storage
```

Clean molly: contexts, accepted host keys, ssh config blocks:

```
docker context rm sw1 sw2
ssh-keygen -R 10.0.0.9
ssh-keygen -R 10.0.0.10
sed -i '/^Host sw1.m swarm1.marsel.is$/,/^$/d; /^Host sw2.m swarm2.marsel.is$/,/^$/d' ~/.ssh/config
```

The sed removes each Host block through the blank line that follows it.
Check `~/.ssh/config` afterwards.

## 10. Kubernetes installation checklist

Every Kubernetes installation answers the same questions; installers
differ only in how many they answer for you. minikube answers all of them
silently, kubeadm leaves CIDR, CNI and client access to you, managed
clouds (EKS/GKE/AKS) answer runtime through CNI and leave client access
and ingress.

| Layer             | This lab                                 |
| ----------------- | ---------------------------------------- |
| Provision VM      | virt-install + preseed                   |
| Container runtime | containerd                               |
| Bootstrap         | kubeadm 1.34.10 on kubernetes.marsel.is  |
| Pod CIDR          | 10.244.0.0/16                            |
| CNI               | flannel                                  |
| Client access     | kubectl on molly, admin.conf via scp     |
| App reachability  | Gateway API impl, parked for March       |
| Automation        | scp by hand now, Ansible in March        |

Production adds a tier the lab skips: HA control plane (3+ nodes, stacked
or external etcd), storage (which CSI driver answers
PersistentVolumeClaims) and auth/RBAC beyond the single admin cert.

CNI switch (flannel to Calico or other): the pod CIDR carries over, Calico
accepts any range at install. No live migration: rip the old CNI out,
install the new one, restart every pod to re-wire. Single node ten
minutes, multi-node effectively a cluster rebuild. A CNI choice now does
not lock a fresh cluster later.

kubeadm needs root (sudo): it writes /etc/kubernetes, generates certs and
talks to the kubelet. kubectl does not: it is a client, the cert in the
kubeconfig is the credential.

## 11. Kubernetes on kubeadm: the redo

The book runs its Kubernetes section on minikube. We redid the whole
section against kubernetes.marsel.is with kubeadm, because minikube hides
every choice from section 10 and puts every address behind its own
container: the API server, NodePorts and the dashboard all needed ssh
tunnels from molly. On kubeadm the node is the host, so NodePort lands on
10.0.0.11 and molly reaches everything directly.

The VM was preseeded for this in advance: no swap partition, containerd,
the 1.34 apt repo with kubeadm/kubelet/kubectl held, br_netfilter and
overlay modules, ip_forward sysctl, SystemdCgroup=true.

### 11.1 Purge minikube

minikube delete removes the whole cluster: control plane, pods,
everything, since it all lives inside the one kicbase container. There is
no pod-only removal below that. On kubernetes.marsel.is:

```
minikube delete
```

The minikube binary, kicbase image and ~/.kube stayed; only the cluster
had to go so kubeadm could have the box.

### 11.2 kubeadm init

On kubernetes.marsel.is:

```
sudo kubeadm init --pod-network-cidr=10.244.0.0/16
```

The flag only tells the cluster which range to hand pod IPs from. It does
not choose a CNI; that is a separate manifest applied afterwards. The
value matches flannel's hardcoded default, so flannel needs no editing.
The range must not collide with the lab LAN (10.0.0.0/24) or the swarm
ingress overlay (10.255.0.0/16).

kubeadm noticed v1.36 upstream and correctly fell back to the held
1.34.10. Init pulls the control plane images through containerd, writes
/etc/kubernetes, generates the CA and certs, starts the control plane as
static pods via the local kubelet and prints three things: the kubeconfig
instructions, the CNI reminder and a kubeadm join line with token and CA
hash for future workers.

### 11.3 kubeconfig, on the node and then on molly

On kubernetes.marsel.is, as printed by init:

```
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

kubectl has no remote-fetch: the config IS the bootstrap, server address
plus client cert and CA baked in as base64. Something has to move the
file once. On molly:

```
scp -r k.m:.kube/ ~
```

The -r pulled the discovery cache along with the config; harmless. From
this point every command in this section ran from molly. kubeadm never
goes on molly: it is not a client, it sets up the machine it runs on.

```
kubectl get nodes
```

NotReady, correctly: no CNI yet.

### 11.4 CNI: flannel

Kubernetes does not ship pod networking. It defines the Container Network
Interface and the cluster stays NotReady, pods Pending, until one
implementation is installed. Flannel chosen: smallest footprint on an 8GB
single node, default CIDR matches init, one DaemonSet doing VXLAN
routing. Calico and Cilium are the heavier alternatives; revisit for
March multi-node.

From molly:

```
kubectl apply -f https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml
```

Serious shops pin a version and vendor the manifest in git rather than
trusting latest at apply time; the March Ansible role should do exactly
that.

kube-flannel went Running, coredns left Pending, the node flipped Ready.

### 11.5 Untaint the control plane

A taint is a repellent on a node: pods refuse to land there unless they
carry the matching toleration. kubeadm taints the control plane so
workloads stay off it, which is right in multi-node and wrong on a single
node, where everything would sit Pending forever. The trailing dash means
remove:

```
kubectl taint nodes --all node-role.kubernetes.io/control-plane-
```

### 11.6 hello-minikube without minikube

```
kubectl create deployment hello-minikube --image=kicbase/echo-server:1.0
kubectl expose deployment hello-minikube --type=NodePort --port=8080
kubectl get services
```

The book's expose has no --port because minikube introspected the
containerPort. kubectl create deployment declares none, so expose fails
with "couldn't find port via --port flag or introspection" until the port
is stated; the echo server listens on 8080.

The payoff, from molly, no tunnel:

```
curl http://10.0.0.11:31837
```

The echo server answered on the node IP directly. That one curl is the
entire difference between minikube and a real node.

### 11.7 lazyraster and the storage deadlock

```
git clone https://github.com/bluewhalebook/docker-up-and-running-3rd-edition.git
kubectl apply -f docker-up-and-running-3rd-edition/chapter_10/kubernetes/lazyraster-service.yaml
```

Result: pod Pending, PersistentVolumeClaim Pending with an empty
STORAGECLASS column. Expected failure: minikube ships a default
StorageClass that answers claims automatically, kubeadm ships none.

Fix, the same provisioner minikube uses a sibling of:

```
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

The claim then showed local-path in get pvc output but stayed Pending,
and describe pod said "pod has unbound immediate PersistentVolumeClaims".
The lesson: default StorageClass assignment happens once, at claim
admission, never retroactively. The get pvc display was showing the
current default, not a binding. A claim created before the default
existed is permanently classless. Reconciliation retries most things;
this is one of the places it does not.

Workaround is recreate:

```
kubectl delete -f docker-up-and-running-3rd-edition/chapter_10/kubernetes/lazyraster-service.yaml
kubectl apply -f docker-up-and-running-3rd-edition/chapter_10/kubernetes/lazyraster-service.yaml
```

Fresh claim bound at creation, local-path provisioned the volume
WaitForFirstConsumer style (volume made on the node the scheduler picked,
after it picked), pod went ContainerCreating then Running in under 30
seconds.

```
kubectl get services
curl http://10.0.0.11:31541
```

404: lazyraster answering with no route at /, HTTP reached the pod. Redo
proven end to end.

### 11.8 Observations

kubectl is a pure API client. Everything is mutual TLS against the API
server on 10.0.0.11:6443, client cert from the kubeconfig, both sides
chained to the cluster CA kubeadm generated. Day-to-day operation needs
no shell on any node; ssh remains for bootstrap and host maintenance
only.

kubeconfig is multi-cluster: clusters, users and contexts in one file,
current-context selects. Nothing in the default UX shows which cluster a
command will hit; the wrong-cluster delete is a famous failure mode.
Parked: per-directory context on molly via direnv (.envrc exports
KUBECONFIG, loads on cd in, unloads on cd out, one directory per cluster
under ~/clusters/), plus kube-ps1 and kubectx as garnish.

Order of operations mostly does not matter (the claim waited for the
provisioner to arrive and got answered) but not always (default
StorageClass assignment is admission-time only). Declarative
reconciliation is the March book's core topic; both the working case and
the exception showed up in one lab.

### 11.9 Tear down

Apps die with the cluster, so deleting them first is optional. On
kubernetes.marsel.is:

```
sudo kubeadm reset -f
```

Reset stops the control plane, wipes /var/lib/etcd, /etc/kubernetes and
the kubelet state. Its own output names what it leaves: CNI config,
iptables rules, kubeconfig files. Remaining cleanup, whenever:

```
sudo rm -rf /etc/cni/net.d
```

On molly:

```
rm -rf ~/.kube
```

iptables residue clears on reboot. Packages stay held and installed; the
VM shuts down and sleeps until March. The lazyraster volume died with its
claim: local-path defaults to reclaimPolicy Delete. Retain is what
production sets when data must outlive claims.
