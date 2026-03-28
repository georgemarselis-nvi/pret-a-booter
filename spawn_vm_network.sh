#!/usr/bin/env bash

# versioned location
## LOCATION="https://repo.almalinux.org/almalinux/9.7/BaseOS/x86_64/os/"
# unversioned location
LOCATION="https://repo.almalinux.org/almalinux/9/BaseOS/x86_64/os/"
/usr/bin/time /usr/bin/virt-install --name bigend.marsel.is --memory 4096 --vcpus 2 --disk pool=default,size=20,format=qcow2 --location "${LOCATION}" --os-variant almalinux9 --boot uefi --network bridge=br-eno2,model=e1000 --graphics none --console pty,target_type=serial --initrd-inject /home/gmarselis/src/pret-a-booter/bigend.marsel.is.ks --extra-args="console=ttyS0,115200n8 inst.ks=file:///bigend.marsel.is.ks ip=10.0.0.4::10.0.0.138:255.255.255.0:bigend.marsel.is:ens1:none nameserver=1.1.1.1 rd.neednet=1" --wait=-1
