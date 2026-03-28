# Version: 0.1
# Host: bigend.marsel.is

text
reboot

lang en_US.UTF-8
keyboard us
timezone Europe/Oslo --utc

network --bootproto=static --ip=10.0.0.4 --netmask=255.255.255.0 --gateway=10.0.0.138 --nameserver=1.1.1.1 --hostname=bigend.marsel.is

bootloader --timeout=1
zerombr
clearpart --all --initlabel --disklabel=gpt
part /boot/efi --fstype=efi --size=1024
part /boot --fstype=xfs --size=2048
part swap --size=4096
part / --fstype=xfs --grow

rootpw --lock
user --name=gmarselis --groups=wheel --password=! --iscrypted
sshkey --username=gmarselis "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIL5G39vHZAQFo6BuFfJtIFUR/4DyQtf9KIIy4jJlcBQt gmarselis@molly.vetinst.no"

%packages
@^minimal-environment
## add
xauth
vim-enhanced
nginx
certmonger
# certbot does what certmonger does manually. not sure if i need it, adding it for now
## certbot
dnsmasq
tftp-server
gnutls
gnutls-utils
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

%post
echo "%wheel ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/gmarselis
# enable services
systemctl enable nginx.service
systemctl enable certmonger.service
systemctl enable dnsmasq.service
systemctl enable tftp.socket
# disable services
systemctl disable fwupd.service
systemctl mask fwupd.service
hostnamectl --static bigend.marsel.is
hostnamectl --pretty bigend
dnf remove -y sssd sssd-common sssd-client
dnf remove -y iwl100-firmware iwl1000-firmware iwl105-firmware iwl135-firmware iwl2000-firmware iwl2030-firmware iwl3160-firmware iwl5000-firmware iwl5150-firmware iwl6000g2a-firmware iwl6050-firmware iwl7260-firmware
# anaconda does not know about epel-release. If you need it, put it here
# declaring it in %packages will hang the installation.
# Needed for several of the packages that follow it.
dnf install -y epel-release
# if you need /usr/bin/audit2allow:
## dnf install -y policycoreutils-python-utils
#
# fail2ban
## fail2ban-selinux.noarch pulls policycoreutils-python-utils
dnf install -y fail2ban.noarch fail2ban-firewalld.noarch fail2ban-mail.noarch fail2ban-selinux.noarch fail2ban-sendmail.noarch fail2ban-server.noarch fail2ban-systemd.noarch fail2ban-tests.noarch
systemctl enable fail2ban.service
#
# cleanup: firewall-cmd goes through the deamon, but the environemnt
# is chrooted. firewall-offline-cmd edits the xml directly
# cleanup: the cockpit package leaves a hole in the firewall
firewall-offline-cmd --remove-service=cockpit
# cleanup: no DHCPv6 on the segment
firewall-offline-cmd --remove-service=dhcpv6-client
# cleanup: we do not need the anaconda cfg files
rm -f /root/anaconda-ks.cfg
# /root/original-ks.cfg gets written way past %end, so it will remain even if we remove it here.

# last upgrade
dnf upgrade -y --refresh

%end

