# prêt-à-booter

Automated PXE/DHCP server deployment for unattended Linux installations.

## What it does

Deploys a PXE host VM on a KVM hypervisor running AlmaLinux 9. Once running,
the PXE host serves the local /24 subnet and installs AlmaLinux 9 on any
machine that network boots - server or desktop, bare metal or VM.

## How it works

- dnsmasq runs in proxy DHCP mode: does not replace the existing DHCP server,
  only answers PXE boot option requests
- GRUB2 EFI served over TFTP for UEFI clients
- nginx serves kickstart files only, blank response for everything else
- AlmaLinux 9 kernel and initrd downloaded from repo
- Kickstart handles unattended install, user setup and post-install configuration

## Requirements

- KVM host running AlmaLinux 9
- A bridge interface attached to the physical network
- Root access on the KVM host
- Internet access for ISO and package downloads

## Usage
```bash
chmod +x deploy-pxehost.sh
./deploy-pxehost.sh
```

The script detects or creates a bridge, finds a free IP, downloads the
AlmaLinux boot ISO, builds and injects a kickstart, and deploys the VM
unattended.

## Design principles

- No USB sticks
- No manual steps after the first run
- Everything defined in code
- Infinitely replicable: only the first machine requires physical access

## License

GPL-3.0
