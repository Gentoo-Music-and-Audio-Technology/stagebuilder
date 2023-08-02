#!/bin/bash

##########################
# Steps in this installer
# 1. User enters disk to install onto
# 2. Disk is partitioned and formatted
# 3. Tarball is installed
# 4. Prepare for chroot and call chroot_install to take over
##########################

# Cannot use comments inside heredoc, so they are here for reference:
# fdisk (device)
# g       # Create GPT label
# n       # New partition
# 1       # Partition number
#         # Default first block (press Enter)
# +1G	  # Partition size
# t       # Set partition type
# 1       # Only one partition, fdisk assumes this one, set it to type 1, EFI. It should have plenty of space for kernels.
# n       # New partition
# 2       # Partition 2
#         # Default first block (press Enter)
# +512M   # Partition size
# t       # Set partition type
# 2       # Choose partition 2
# 19      # Set partition to type swap. It's small because this is just a token swap partition. It should never get used for audio.
# n       # New partition
# 3       # Partition 3
#         # Default first block (press Enter)
#         # Default last block (press Enter). This is the main partition.
# w       # Save partition table & quit

set -e # Do not proceed if something goes wrong.

mntpoint="/mnt/gentoo" # Don't use trailing slash here.
tarball_file="decibellinux-stage4.tar.bz2" # Useful for changing the filename for testing purposes.

dialog --msgbox "\
Use arrow keys to scroll up/down inside this box.\
\n\n\
Pre-installation notes:\
\n\n\
This installer assumes it is using a modern EFI system.\
\n\n\
If you want to dual-boot with Windows, exit installer and use the manual install instructions on decibellinux.org.\
\n\n\
You need to choose a disk to install decibel Linux onto.\
\n\n\
You should choose a disk that is either blank or does not contain data you want to keep.\
\n\n\
ONCE YOU SELECT A DISK, EVERYTHING ON IT WILL BE ERASED.\
\n\n\
The installer will now show you the available disks on your system. It assumes disks are either /dev/sd* or /dev/nvme*.\
\n\n\
This installer assumes you know how to choose a disk to install on.\
\n\n\
The installer will download a file that is around 3 GB in size. This is the main installation package. It is not optional." 20 50

# CHOOSE DISK TO INSTALL DECIBEL LINUX ONTO

alldisks=$(lshw -class disk | grep '/dev/nvme\|/dev/sd')
alldisks=${alldisks//logical name: /}

devices=$(echo $alldisks | tr "\n" "\n")
count=1
for device in $devices
do
  	alldevices="${alldevices} $device \"Device_$count\""
        ((count=count+1))
done

# Output is redirected so it can be stored in a var, instead of writing to a file and then reading the file. 
installdevice=$(whiptail --title "Choose a disk to install onto:" --menu "Choose an option" 25 78 16 $alldevices 3>&1 1>&2 2>&3)

# Manual entry for previous version of installer required a check to make sure the install device was valid.
# Since user is now selecting from a list, this is no longer necessary.

### PARTITION DISK, SEE COMMENTS ABOVE

fdisk $installdevice << FDISK_CMDS
g
n
1

+1G
t
1
n
2

+512M
t
2
19
n
3


w
FDISK_CMDS

### Create filesystems
# If /dev/nvme0n1, then parts must be p1, p2, p3

if [[ $installdevice == *"/dev/nvme"* ]]; then
	part="p1"
else
	part="1"
fi
mkfs.fat -F 32 $installdevice$part

if [[ $installdevice == *"/dev/nvme"* ]]; then
	part="p3"
else
	part="3"
fi
mkfs.ext4 $installdevice$part

if [[ $installdevice == *"/dev/nvme"* ]]; then
	part="p2"
else
	part="2"
fi
mkswap $installdevice$part
swapon $installdevice$part

### Install base system

mkdir -p $mntpoint/boot
if [[ $installdevice == *"/dev/nvme"* ]]; then
	part="p3"
else
	part="3"
fi
mount $installdevice$part $mntpoint

cd $mntpoint
wget --no-check-certificate https://decibellinux.org/src/$tarball_file
echo "Unpacking system. This could take a minute or two. Please be patient..."
tar xjpf $tarball_file --xattrs --numeric-owner
echo "System unpacked."

cp $mntpoint/usr/share/portage/config/repos.conf $mntpoint/etc/portage/repos.conf/gentoo.conf
cp -L /etc/resolv.conf $mntpoint/etc/
# Kernel is in /boot, so we need to move kernel files out of the way to mount sda1
mkdir $mntpoint/kernfiles
mv $mntpoint/boot/* $mntpoint/kernfiles/

# The following must account for M.2 drives (p1)
if [[ $installdevice == *"/dev/nvme"* ]]; then
	part="p1"
else
	part="1"
fi
mount $installdevice$part $mntpoint/boot
mv /mnt/gentoo/kernfiles/* $mntpoint/boot/

### Chroot into system and run chroot_install

mount -t proc /proc $mntpoint/proc
mount --rbind /sys $mntpoint/sys
mount --rbind /dev $mntpoint/dev
mount --make-rslave $mntpoint/sys
mount --make-rslave $mntpoint/dev
mount --bind /run $mntpoint/run
mount --make-slave $mntpoint/run

wget --no-check-certificate -O chroot_install.sh https://decibellinux.org/src/chroot_install.sh
chmod +x chroot_install.sh
echo "$installdevice" > installdevice.txt
cp -L /etc/resolv.conf $mntpoint/etc/
chroot $mntpoint/ ./chroot_install.sh

# Post chroot_install cleanup:
rm $mntpoint/chroot_install.sh
rm $mntpoint/$tarball_file
umount -l $mntpoint/dev{/shm,/pts,}
umount -l $mntpoint/proc
umount -l $mntpoint/sys
umount -l $mntpoint/run

# Install complete notification
whiptail --msgbox --title "Installation complete" \
"Install complete. Remove/disable the boot medium you used and reboot.\n\
Don't forget to select Xfce Session in the upper right corner when you first log in." 0 0
