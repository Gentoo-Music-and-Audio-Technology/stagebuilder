# Continued from autobuild.sh

# set -e is !needed here bec it is called by a script outside chroot that uses set -e already.

builddir="/var/tmp/stagebuilder"
usepkg="getbinpkg" # Choose between getbinpkg and -getbinpkg. Useful for troubleshooting and rebuilding the binhost.
exclude_list="virtual/* sys-kernel/*-sources acct-group/* acct-user/* app-eselect/* sys-kernel/*-firmware"

### PREP BEFORE PKG INSTALLATION

source /etc/profile

mkdir -p /etc/portage/repos.conf
cp /usr/share/portage/config/repos.conf /etc/portage/repos.conf/gentoo.conf
emerge-webrsync

# Audio config
cat > /etc/sysctl.conf <<EOF
vm.swappiness = 10
dev.rtc.max-user-freq=3072
dev.hpet.max-user-freq=3072
EOF
mkdir -p /etc/security/limits.d
cat > /etc/security/limits.d/audio.conf <<EOF
@audio - rtprio 95
@audio - memlock unlimited
EOF
cat > /etc/udev/rules.d/firewire.rules <<EOF
KERNEL=="fw0", GROUP="audio", MODE="0664"
KERNEL=="fw1", GROUP="audio", MODE="0664"
KERNEL=="fw2", GROUP="audio", MODE="0664"
EOF
cat > /etc/udev/rules.d/timer-permissions.rules <<EOF
KERNEL=="rtc0", GROUP="audio"
KERNEL=="hpet", GROUP="audio"
EOF
cat > /etc/udev/rules.d/99-cpu-dma-latency.rules <<EOF
DEVPATH=="/devices/virtual/misc/cpu_dma_latency", OWNER="root", GROUP="audio", MODE="0660"
EOF

mkdir -p /usr/lib64/lv2
ln -s /usr/lib64/lv2/ /usr/lib/lv2 # To be standards-compliant and allow Ardour to scan /usr/lib64/lv2

# Set up repo
# This should eventually be changed to decibelLinux
mkdir -p /var/db/repos/decibellinux/metadata/
cat > /etc/portage/repos.conf/decibelLinux.conf <<EOF
[GentooStudio]
location = /var/db/repos/gentoostudio
sync-type = git
sync-uri = https://github.com/Gentoo-Music-and-Audio-Technology/gentoostudio.git
auto-sync = yes
EOF

# make.conf
# Temporarily set EMERGE_DEFAULT_OPTS
cat >> /etc/portage/make.conf <<EOF
ALSA_CARDS="*"
EMERGE_DEFAULT_OPTS="--quiet"
FEATURES="getbinpkg"
BINPKG_FORMAT="gpkg"
PORTAGE_BINHOST="https://decibellinux.org/src/binpkgs"
CONFIG_PROTECT="protect-owned"
ACCEPT_LICENSE="-* @FREE @BINARY-REDISTRIBUTABLE"
GRUB_PLATFORMS="efi-64"
USE="aacplus audacious cddb cdio consolekit corefonts dssi encode equalizer faac ffmpeg fftw fluidsynth freesound
gudev gtk3 hwdb id3 id3tag ieee1394 jack ladspa lame libsamplerate lv2 matroska midi minizip mpg123 musepack musicbrainz
netjack opus pcre16 python qt3support quicktime realtime rubberband shine shout skins sndfile soundtouch
taglib theora timidity twolame vamp vcd vst wav wavpack xine xkb xvfb xvmc -branding -pulseaudio -xscreensaver"
EOF

cat >> /etc/os-release <<EOF
NAME=decibelLinux
ID=decibellinux
PRETTY_NAME="decibel Linux"
ANSI_COLOR="1;32"
HOME_URL="https://www.decbibellinux.org/"
SUPPORT_URL="https://www.decibellinux.org/"
BUG_REPORT_URL="https://decibellinux.org/"
EOF

# package.*
cd
echo "Fetching portage config files (/etc/portage/*)..."
wget --quiet -r -np -R "index.html*" https://decibellinux.org/src/etc/
cd decibellinux.org/src/etc/portage
cp -r * /etc/portage
cd
rm -rf decibellinux.org
echo "Done."

# buildpkg and usepkg used here to cut down on build time.
FEATURES="$usepkg" emerge --ask=n --buildpkg --buildpkg-exclude "$exclude_list" dev-vcs/git # Needed to sync decibel Linux repo.
emaint sync
FEATURES="$usepkg" emerge --ask=n --quiet --update --deep --newuse --buildpkg --buildpkg-exclude "$exclude_list" @world
eselect news read all # Old news is not relevant to new users

# Install pkgs for decibel Linux, and also build binaries
# Something is wrong here. Script skips to locales at this point.
#while read p; do
#	emerge --ask=n --buildpkg --usepkg --buildpkg-exclude "virtual/* sys-kernel/*-sources" $p
#done <packages
FEATURES="$usepkg" emerge --ask=n --buildpkg --buildpkg-exclude "$exclude_list" \
app-portage/cpuid2cpuflags \
app-portage/eix \
app-portage/genlop \
app-portage/gentoolkit \
app-portage/smart-live-rebuild \
app-portage/ufed \
dev-util/geany \
gnome-extra/nm-applet \
media-plugins/adlplug \
media-plugins/airwindows \
media-plugins/alsa-plugins \
media-plugins/argotlunar \
media-plugins/artyfx \
media-plugins/calf \
media-plugins/cardinal \
media-plugins/distrho-ports \
media-plugins/dragonfly-reverb \
media-plugins/drumgizmo \
media-plugins/fabla \
media-plugins/lsp-plugins-lv2 \
media-plugins/odin \
media-plugins/opnplug \
media-plugins/sorcer \
media-plugins/x42-avldrums \
media-plugins/x42-plugins \
media-plugins/zam-plugins \
media-sound/a2jmidid \
media-sound/aeolus \
media-sound/aliki \
media-sound/alsa-tools \
media-sound/alsa-utils \
media-sound/amsynth \
media-sound/ardour \
media-sound/arpage \
media-sound/audacious \
media-sound/audacity \
media-sound/bitmeter \
media-sound/bristol \
media-sound/butt \
media-sound/cadence \
media-sound/carla \
media-sound/chuck \
media-sound/din \
media-sound/fluidsynth \
media-sound/galan \
media-sound/ghostess \
media-sound/gmidimonitor \
media-sound/hydrogen \
media-sound/hydrogen-drumkits \
media-sound/jack-rack \
media-sound/jack2 \
media-sound/jackmidiclock \
media-sound/jamin \
media-sound/japa \
media-sound/linuxsampler \
media-sound/lmms \
media-sound/luppp \
media-sound/mixxx \
media-sound/new-session-manager \
media-sound/patchage \
media-sound/pure-data \
media-sound/qjackctl \
media-sound/qmidiarp \
media-sound/qsampler \
media-sound/qtractor \
media-sound/rosegarden \
media-sound/terminatorx \
media-sound/timemachine \
media-sound/tk707 \
media-sound/vmpk \
media-sound/yoshimi \
net-misc/dhcpcd \
net-misc/networkmanager \
sys-apps/usbutils \
sys-boot/grub \
sys-boot/plymouth \
sys-kernel/dracut \
sys-kernel/genkernel \
sys-kernel/linux-firmware \
sys-kernel/rt-sources \
x11-base/xorg-server \
x11-misc/lightdm \
x11-misc/mugshot \
xfce-base/xfce4-meta \
xfce-extra/xfce4-whiskermenu-plugin \
xfce-extra/xfce4-alsa-plugin \
xfce-base/xfce4-power-manager || die "Packages were not merged. Quitting."

# Need code here to generate list of default installed apps based the packages file.

# Config kernel
# Kernel has to be genkernelled now to generate a .config. Make bzImage only to save time.
eselect kernel set 1
genkernel bzImage
# Fully premptible kernel. Expert is required to select full RT
sed -i 's/# CONFIG_EXPERT is not set/CONFIG_EXPERT=y/' /usr/src/linux/.config
sed -i 's/CONFIG_PREEMPT_BUILD=y/CONFIG_PREEMPT_LAZY=y/' /usr/src/linux/.config
sed -i 's/CONFIG_PREEMPT_VOLUNTARY=y/CONFIG_PREEMPT_RT=y/' /usr/src/linux/.config
sed -i 's/CONFIG_PREEMPT_DYNAMIC=y/# CONFIG_PREEMPT_DYNAMIC=y/' /usr/src/linux/.config
# Speculation mitigations security intereferes with real-time operations
sed -i 's/CONFIG_SPECULATION_MITIGATIONS=y/# CONFIG_SPECULATION_MITIGATIONS is not set/' /usr/src/linux/.config
# Default CPU freq should be performance
sed -i 's/# CONFIG_CPU_FREQ_DEFAULT_GOV_PERFORMANCE is not set/CONFIG_CPU_FREQ_DEFAULT_GOV_PERFORMANCE=y/' /usr/src/linux/.config
sed -i 's/CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y/# CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL is not set/' /usr/src/linux/.config
# Save a cp of the config for safekeeping.
cp /usr/src/linux/.config /usr/src/linux/.config_full_preempt
# Now run genkernel again to make this take effect.
# genkernel will run a silent make oldconfig, accepting the default changes relevant to config_preempt.
genkernel --kernel-config=/usr/src/linux/.config_full_preempt all
# Get rid of old kernels from previous build runs
rm /boot/*.old

### Enable default services
systemctl enable lightdm
systemctl enable NetworkManager
systemctl enable dhcpcd

### Customize default appearance
# Current GTK theme/icons is Amy-Dark
echo "Fetching Xfce4 config files..."
wget --quiet https://decibellinux.org/src/xfce/xfce4-desktop.xml
wget --quiet https://decibellinux.org/src/xfce/xfce4-panel.xml
wget --quiet https://decibellinux.org/src/xfce/xsettings.xml
wget --quiet https://decibellinux.org/src/img/decibelLinux2023.png
wget --quiet https://decibellinux.org/src/theme/Amy-Dark-GTK.tar.gz
wget --quiet https://decibellinux.org/src/theme/Amy-Dark-Icons.tar.gz
echo "Done."
echo "Fetching bootsplash files..."
wget --quiet -r -np -R "index.html*" https://decibellinux.org/src/plymouth/cybernetic/
echo "Done."
echo "Moving config files..."
mv xfce4-desktop.xml /etc/xdg/xfce4/xfconf/xfce-perchannel-xml/
mv xfce4-panel.xml /etc/xdg/xfce4/xfconf/xfce-perchannel-xml/
mv xsettings.xml /etc/xdg/xfce4/xfconf/xfce-perchannel-xml/
mv decibelLinux2023.png /usr/share/backgrounds/xfce/
tar xzf Amy-Dark-GTK.tar.gz
mv Amy-Dark-GTK /usr/share/themes
tar xzf Amy-Dark-Icons.tar.gz
mv Amy-Dark-Icons /usr/share/icons
mv decibellinux.org/src/plymouth/cybernetic /usr/share/plymouth/themes/
rm Amy-Dark-GTK.tar.gz
rm Amy-Dark-Icons.tar.gz
echo "Done."

# Enable all locales and allow user to narrow it down if they choose to.
# Change this to allow user to select locale.
cp /usr/share/i18n/SUPPORTED /etc/locale.gen
locale-gen --quiet

cat > /etc/default/grub <<EOF
GRUB_DISTRIBUTOR="decibel"
GRUB_DISABLE_LINUX_PARTUUID=false
GRUB_DISABLE_OS_PROBER=false
GRUB_CMDLINE_LINUX_DEFAULT='quiet splash'
GRUB_GFXMODE=1366x768x24
GRUB_GFXPAYLOAD_LINUX=keep
EOF

# This reduces the tarball size by rm'ing !needed files.
rm -rf /var/cache/distfiles/*
rm -rf /usr/src/linux/*
rm -rf /var/db/repos/* # Will be webrsync'd during install anyway
rm -rf /var/tmp/*

# Exit chroot
exit
