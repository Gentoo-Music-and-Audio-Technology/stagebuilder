#!/bin/bash

#################################
# STEPS THIS INSTALLER TAKES
# 1. . /etc/profile
# 2. Read install device (ex: /dev/sda)
# 3. Configure fstab
# 4. Configure grub
# 5. Users and passwords
# 6. Name your computer
# 7. Configure make.conf
# 8. System update
# 9. Cleanup
# 10. Parting advice
#################################

source /etc/profile

# Read from the install device file set pre-chroot
file="installdevice.txt"
while read -r line; do
        installdevice="$line"
done <$file

### TESTING STEP
#echo "Installing to: $installdevice"
#exit 1;

# /etc/fstab
# Store parts in vars, otherwise bash will think the numbers are part of the vars
# Must accoubt for M.2 drives (p1, p2, p3)
if [[ $installdevice == *"/dev/nvme"* ]]; then
        bootpart="p1"
	rootpart="p3"
	swappart="p2"
else
        bootpart="1"
	rootpart="3"
	swappart="2"
fi
cat > /etc/fstab <<EOF
$installdevice$bootpart	/boot	vfat	defaults,noatime	0 2
$installdevice$rootpart	/	ext4	noatime			0 1
$installdevice$swappart	none	swap	sw			0 0
EOF

# Grub & bootsplash
grub-install --target=x86_64-efi --efi-directory=/boot --removable
plymouth-set-default-theme cybernetic
dracut --force
grub-mkconfig -o /boot/grub/grub.cfg

# Passwords
echo "Enter a password for root:"
passwd
echo "Enter a regular username to use:"
read reguser
useradd -m -G users,wheel,audio,plugdev -s /bin/bash $reguser
echo "Enter a password for $reguser:"
passwd $reguser

# Configure user home dir, workaround until I figure out how to change Xfce4 defaults
# Other Xfce4 config files seem to get picked up from /etc/xdg, why not desktop?
mkdir -p /home/$reguser/.config/xfce4/xfconf/xfce-perchannel-xml
wget --no-check-certificate https://decibellinux.org/src/xfce4-desktop.xml
mv xfce4-desktop.xml /home/$reguser/.config/xfce4/xfconf/xfce-perchannel-xml
mkdir -p /home/$reguser/Desktop # Just in case
wget https://gentoostudio.org/src/xfce/Welcome.txt
mv Welcome.txt /home/$reguser/Desktop # We only care about THIS user. Other users will not get this file.
chown -R $reguser:$reguser /home/$reguser

# Computer name
# Now handled by systemd-firstboot
#echo "Enter a name for your computer:"
#read computer_name
#hostnamectl hostname $computer_name

# Set timezone with timedatectl
# Results in "too few arguments" being thrown
tzones=( $(timedatectl list-timezones) )
list=$(timedatectl list-timezones | cat -n)
zonenum=$(whiptail --title "Time zone" --menu "Select your time zone" 25 78 16 $list 3>&1 1>&2 2>&3)
timedatectl set-timezone ${tzones[$((zonenum-1))]}
echo "Time zone set to ${tzones[$((zonenum-1))]}"

# Set locale here

# Config make.conf
cpuflags=$(cpuid2cpuflags)
flags=${cpuflags/: /=\"}
endquote="\""
echo "$flags$endquote" >> /etc/portage/make.conf
# This is not the best way to set MAKEOPTS. If nproc==1, MAKEOPTS=0, which causes emerge to fail.
#numjobs=$(($(nproc)-1))
#echo "MAKEOPTS=\"-j$numjobs\"" >> /etc/portage/make.conf
# At this point everything going forward can be compiled for this user's architecture.
# Or maybe not - changing CFLAGS could mean the binhost gets ignored.
#sed -i 's/COMMON_FLAGS="-O2 -pipe"/COMMON_FLAGS="-march=native -O2 -pipe"/' /etc/portage/make.conf

systemd-firstboot --prompt --setup-machine-id
systemctl preset-all --preset-mode=enable-only

# Cleanup
rm installdevice.txt
rm -rv /kernfiles
rm stage4-amd64-latest.tar.bz2

# System update to incorporate newly set flags
# This update is no longer optional. This could help with troubleshooting.
emerge-webrsync
eix-sync # Temp set default opts to avoid asking user to proceed with sync
# "Less than a minute" is very far off the mark.
#eut=$(emerge -puDN --keep-going --with-bdeps=y --backtrack=250 @system @world | genlop -np | grep 'Estimated update time')
whiptail --msgbox --title "Required system update" "\
Installer will now perform a system update. This could take a little time but is necessary.
\n This update will do two things:
1. Update any installed packages to latest available versions, and
2. Allow installed packages to take advantage of CPU-specific instructions. (For example, ffmpeg and fftw do this.)
\n It is highly recommended to update your system regularly, such as weekly or monthly at the latest.
\n Instructions for updating your system can be found at https://decibellinux.org.
\n decibel Linux is a rolling release system so waiting too long to update could be tricky." 0 0
FEATURES="getbinpkg" emerge -uDN --keep-going --with-bdeps=y --backtrack=250 @system @world

# Set EMERGE_DEFAULT_OPTS for users
sed -i 's/EMERGE_DEFAULT_OPTS="--quiet"/EMERGE_DEFAULT_OPTS="--quiet --ask --ask-enter-invalid --autounmask-license=y --autounmask-write=y"/' /etc/portage/make.conf

exit # Return to calling script
