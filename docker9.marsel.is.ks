# Version: 0.1
# Host: docker9.marsel.is
# Tear down, from molly:
# virsh --connect qemu+ssh://3jane/system destroy docker9.marsel.is; virsh --connect qemu+ssh://3jane/system undefine docker9.marsel.is --nvram --remove-all-storage
# After roll, from molly:
# ssh -o StrictHostKeyChecking=accept-new docker9.marsel.is
# Roll, from molly:
# /usr/bin/time /usr/bin/virt-install --connect qemu+ssh://3jane/system --name docker9.marsel.is --memory 4096 --vcpus 2 --disk pool=default,size=40,format=qcow2 --location https://repo.almalinux.org/almalinux/9.8/BaseOS/x86_64/os/ --os-variant almalinux9 --boot uefi --network bridge=br-eno2,model=e1000 --graphics none --console pty,target_type=serial --initrd-inject /home/gmarselis/src/pret-a-booter/docker9.marsel.is.ks --extra-args="console=ttyS0,115200n8 inst.text inst.ks=file:/docker9.marsel.is.ks" --wait=-1

text
reboot

# Locale
lang en_US.UTF-8
keyboard us

# Clock
timezone Europe/Oslo --utc

# Network
network --bootproto=static --ip=10.0.0.16 --netmask=255.255.255.0 --gateway=10.0.0.138 --nameserver=1.1.1.1 --hostname=docker9.marsel.is

# Mirror
url --url=https://repo.almalinux.org/almalinux/9.8/BaseOS/x86_64/os/
repo --name=AppStream --baseurl=https://repo.almalinux.org/almalinux/9.8/AppStream/x86_64/os/

# Partitioning
bootloader --timeout=1 --append="console=ttyS0,115200n8"
zerombr
clearpart --all --initlabel --disklabel=gpt
part /boot/efi --fstype=efi --size=512
part /boot --fstype=ext4 --size=1024
part swap --size=4096
part / --fstype=xfs --grow

# Root account disabled
rootpw --lock

# User
user --name=gmarselis --groups=wheel --password=! --iscrypted
sshkey --username=gmarselis "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIL5G39vHZAQFo6BuFfJtIFUR/4DyQtf9KIIy4jJlcBQt gmarselis@molly.vetinst.no"
sshkey --username=gmarselis "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDFEXqWvm+k3k+UNq+c66di1Dav5bOact+DzstO8vrjX gmarselis@3jane.vetinst.no"

# Packages
%packages
@^minimal-environment
## add
xauth
vim-enhanced
ca-certificates
curl
gnupg2
parted
nmap
dnf-plugins-core
gnutls-utils
openldap-clients
## remove
-polkit
-polkit-pkla-compat
# if you are treating the vm as cattle, you do not need qemu-guest-agent
-qemu-guest-agent
-cockpit
-cockpit-bridge
-cockpit-system
-cockpit-ws
%end

%addon com_redhat_kdump --disable
%end

# Post-install
%post --log=/root/ks-post.log
echo "%wheel ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/gmarselis
/usr/bin/chmod 440 /etc/sudoers.d/gmarselis
# make sure the machine is named before anything else
/usr/bin/hostnamectl --static docker9.marsel.is
/usr/bin/hostnamectl --pretty docker9
# disable services
/usr/bin/systemctl disable fwupd.service
/usr/bin/systemctl mask fwupd.service
/usr/bin/dnf remove -y sssd sssd-common sssd-client
/usr/bin/dnf remove -y iwl100-firmware iwl1000-firmware iwl105-firmware iwl135-firmware iwl2000-firmware iwl2030-firmware iwl3160-firmware iwl5000-firmware iwl5150-firmware iwl6000g2a-firmware iwl6050-firmware iwl7260-firmware
# anaconda does not know about epel-release. If you need it, put it here
# declaring it in %packages will hang the installation.
# Needed for several of the packages that follow it.
/usr/bin/dnf install -y epel-release

## firewall
# firewall-cmd goes through the daemon, but the environment
# is chrooted. /usr/bin/firewall-offline-cmd edits the xml directly
#
# the cockpit package leaves a hole in the firewall
/usr/bin/firewall-offline-cmd --remove-service=cockpit
# no DHCPv6 on the segment
/usr/bin/firewall-offline-cmd --remove-service=dhcpv6-client

## cleanup
# /root/original-ks.cfg gets written way past %end, so it will remain even if we remove it here.
# anaconda leaves /var/log/anaconda after install, we do not need it
/usr/bin/cat > /etc/systemd/system/cleanup-install.service << 'EOF'
[Unit]
Description=Remove anaconda installation artifacts
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/rm -rf /var/log/anaconda
ExecStart=/usr/bin/rm -f /root/anaconda-ks.cfg /root/original-ks.cfg
ExecStartPost=/usr/bin/systemctl disable cleanup-install.service
ExecStartPost=/usr/bin/rm -f /etc/systemd/system/cleanup-install.service

[Install]
WantedBy=multi-user.target
EOF

/usr/bin/systemctl enable cleanup-install.service

###################################################################################################
# Configuration
#   This eventually will run in Ansible
###################################################################################################
#
# SSHd: allow logins exclusively by openssh public key
/usr/bin/sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/'      /etc/ssh/sshd_config    # disable password   auth
/usr/bin/sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/'         /etc/ssh/sshd_config    # enable  public key auth
/usr/bin/sed -i 's/^#*AuthenticationMethods.*/AuthenticationMethods publickey/' /etc/ssh/sshd_config    # enable  public key auth only
/usr/bin/sed -i 's/^#*GSSAPIAuthentication.*/GSSAPIAuthentication no/'          /etc/ssh/sshd_config    # disable kerberos   auth

#
# Docker CE: not in AlmaLinux, comes from download.docker.com
/usr/bin/dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
/usr/bin/dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin
/usr/bin/systemctl enable docker.service
/usr/sbin/usermod -aG docker gmarselis

#
# The Last Upgrade
/usr/bin/dnf upgrade -y --refresh

# install epel-release packages that could not be installed before the repo was configured
/usr/bin/dnf install -y ncdu
/usr/bin/dnf install -y etckeeper

# etckeeper: init now, first commit after first boot
/usr/bin/etckeeper init
/usr/bin/cat > /etc/systemd/system/etckeeper-initial-commit.service << 'EOF'
[Unit]
Description=etckeeper initial commit
After=network.target
ConditionPathExists=!/etc/.git/refs/heads/main

[Service]
Type=oneshot
ExecStart=/usr/bin/etckeeper commit "Initial post-install commit"
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

/usr/bin/systemctl enable etckeeper-initial-commit.service

%end
