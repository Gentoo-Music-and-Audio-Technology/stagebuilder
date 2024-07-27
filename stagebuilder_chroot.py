#!/usr/bin/env python
# Chroot program for Stagebuilder. Should only be called by stagebuilder.py.
# Any sys.exit() here will throw control back to stagebuilder.py outside of chroot.

import os
import subprocess
import requests
import sys
from pathlib import Path
import stagebuilder_class as sb

sb.normal_msg("Now running chroot program.")

sb.normal_msg(f"Selected kernel is {sb.KERNEL_TYPE}-{sb.KERNEL_VER}.")

# Finish up chroot preparation:
sb.normal_msg("Finishing up chroot prep...")
sb.normal_msg("Running source /etc/profile...")
subprocess.run(['source /etc/profile'], shell=True, check=True)
sb.normal_msg("Creating EFI dir...")
subprocess.run(['mkdir /efi'], shell=True, check=True)
#sb.normal_msg("Installing dosfstools...")
#subprocess.run(['emerge --ask=n --quiet sys-fs/dosfstools'], shell=True, check=True)
sb.normal_msg("Mounting vfat partition on EFI dir...")
subprocess.run(['mount /dev/sdb1 /efi'], shell=True, check=True) # This will let us install grub and linux-firmware. /dev/sdb is a fat32 partition created for this purpose.
sb.normal_msg("Syncing repos...")
subprocess.run(['emerge-webrsync'], shell=True, check=True)
sb.normal_msg("Emerging dev-vcs/git...") # One test run failed to sync because git was not found. Including now to prevent such failure.
subprocess.run(['emerge --ask=n --quiet --buildpkg --usepkg dev-vcs/git'], shell=True, check=True)
sb.normal_msg("Successfully emerge git.")
sb.normal_msg("Running emerge --sync...")
subprocess.run(['emerge --sync --ask=n --quiet'], shell=True, check=True)
sb.normal_msg("Marking all news as read...")
subprocess.run(['eselect news read all'], shell=True, check=True) # Clear news notifications for new users.
sb.normal_msg("Setting profile and updating...")
subprocess.run(['eselect profile set 24'], shell=True, check=True) # Sets  [24]  default/linux/amd64/23.0/desktop/systemd (stable)
subprocess.run(['emerge --ask=n --quiet --verbose --update --deep --newuse --buildpkg --usepkg @world'], shell=True, check=True)
sb.normal_msg("Successfully completed chroot prep.")

### INSTALL SOFTWARE

# Read from stage4_packages file and install all specified packages:
# If this section fails, we need to parse the error message to see if it was because an emerge failed due to "could not resolve"
# or a failure to reach github.com. If this happened, simply run the script again, because there is nothing anyone except the
# server maintainers can do about that.
# Also, the VM may have lost connection. If so, the VM may need to be rebooted.
# Could some kind of monitoring program handle this? Would restarting the virtualbox service help?
if sb.INSTALL_SOFTWARE:
    sb.normal_msg("Installing software from stagebuilder_pkgs...")
    with open("stagebuilder_pkgs") as fp:
        for line in fp:
            if "#" not in line and not line.isspace():
                sb.normal_msg(f"Installing {line}...")
                # --buildpkg and --usepkg are for stagebuilder's cache feature.
                subprocess.run([f"emerge --ask=n --quiet --buildpkg --usepkg {line}"], shell=True, check=True)
else:
    sb.normal_msg("Not installing additional software.")

### KERNEL CONFIG 

# Firmware
sb.normal_msg("Installing firmware...")
subprocess.run(['emerge --quiet --buildpkg --usepkg --ask=n sys-kernel/linux-firmware'], shell=True, check=True)
subprocess.run(['emerge --quiet --buildpkg --usepkg --ask=n sys-firmware/sof-firmware'], shell=True, check=True)
subprocess.run(['emerge --quiet --buildpkg --usepkg --ask=n sys-firmware/intel-microcode'], shell=True, check=True)
sb.normal_msg("Successfully installed firmware.")

if sb.AUTOFIND_RT_PATCH:
    # All this if statement needs to do is swap out existing values.
    rt_patch_version = sb.autofind_latest_rt_patch()
    sb.KERNEL_VER = rt_patch_version[0]
    sb.RT_PATCH_URL = f"{sb.RT_PATCHES_BASE_URL}{rt_patch_version[1]}/"
    sb.RT_PATCH_FILE = rt_patch_version[2]
    # The else is implied by user-set values in stagebuilder_class.py.

# Install bootloader, generkenel and selected kernel:
sb.normal_msg("Installing selected kernel...")
if sb.SPECIFY_KERNEL: # Specify exact version.
    subprocess.run([f'emerge --buildpkg --usepkg --ask=n --quiet ={sb.KERNEL_TYPE}-{sb.KERNEL_VER}'], shell=True, check=True)
    sb.normal_msg("Succesfully installed kernel sources.")
else: # Just install the latest stable version of the specified type.
    subprocess.run([f"emerge --buildpkg --usepkg --ask=n --quiet {sb.KERNEL_TYPE}"], shell=True, check=True)
sb.normal_msg("Ensuring kernel is set by eselect...")
subprocess.run(['eselect kernel set 1'], shell=True, check=True)
sb.normal_msg("Installing genkernel...")
subprocess.run(['emerge --buildpkg --usepkg --ask=n --quiet sys-kernel/genkernel'], shell=True, check=True)
sb.normal_msg("Installing grub...")
subprocess.run(['emerge --buildpkg --usepkg --ask=n --quiet sys-boot/grub'], shell=True, check=True)

# Before applying RT patch, we may want to consider running make allmodconfig.
# While this would bloat the kernel, it would ensure maximum compatibility.
# Something I ran into on a late model MSI laptop, which failed to find the root device with the default kernel config.
# Disable: search for vbox and disable the results. Disable main Virtualization Drivers branch.
# Disable main Virtualization branch.

# Get and apply RT patch and change kernel config to use it:
if sb.USE_RT_PATCH:
    os.chdir("/usr/src/linux")
    sb.normal_msg("Fetching RT patch...")
    response = requests.get(f"{sb.RT_PATCH_URL}{sb.RT_PATCH_FILE}", stream=True)
    response.raise_for_status()
    with open(sb.RT_PATCH_FILE, mode="wb") as file: # Fetch actual patch file.
        for chunk in response.iter_content(chunk_size=10 * 1024):
            file.write(chunk)
    sb.normal_msg(f"Patch saved as {sb.RT_PATCH_FILE}.")
    sb.normal_msg("Applying RT patch...")
    subprocess.run([f'xzcat {sb.RT_PATCH_FILE} | patch -p1'], shell=True, check=True)
    # Configure kernel:
    sb.normal_msg("Generating kernel config...")
    #subprocess.run(["make defconfig"], shell=True, check=True) # This results in a genkernel compile failure. Not sure why.
    subprocess.run(['genkernel bzImage'], shell=True, check=True) # Do just enough so that there's a config file to work with.
    # Check for presence of .config file:
    kernel_config_file = Path("/usr/src/linux/.config")
    if kernel_config_file.exists():
        sb.normal_msg("Kernel config file found. Proceeding.")
    else:
        sb.bailout("Kernel config file not found. You need to fix this before proceeding. Exiting now.", sb.get_linenum())
    # Edit kernel config to use full preemption
    sb.normal_msg("Modifying kernel config to make full preempt the default...")
    subprocess.run(["sed -i 's/# CONFIG_EXPERT is not set/CONFIG_EXPERT=y/' /usr/src/linux/.config"], shell=True, check=True)  
    subprocess.run(["sed -i 's/CONFIG_PREEMPT_BUILD=y/CONFIG_PREEMPT_LAZY=y/' /usr/src/linux/.config"], shell=True, check=True)
    subprocess.run(["sed -i 's/CONFIG_PREEMPT_VOLUNTARY=y/CONFIG_PREEMPT_RT=y/' /usr/src/linux/.config"], shell=True, check=True)
    subprocess.run(["sed -i 's/CONFIG_PREEMPT_DYNAMIC=y/# CONFIG_PREEMPT_DYNAMIC=y/' /usr/src/linux/.config"], shell=True, check=True)
    # Speculation mitigations security intereferes with real-time operations.
    subprocess.run(["sed -i 's/CONFIG_SPECULATION_MITIGATIONS=y/# CONFIG_SPECULATION_MITIGATIONS is not set/' /usr/src/linux/.config"], shell=True, check=True)
    # Default CPU freq should be performance
    subprocess.run(["sed -i 's/# CONFIG_CPU_FREQ_DEFAULT_GOV_PERFORMANCE is not set/CONFIG_CPU_FREQ_DEFAULT_GOV_PERFORMANCE=y/' /usr/src/linux/.config"], shell=True, check=True)
    subprocess.run(["sed -i 's/CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y/# CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL is not set/' /usr/src/linux/.config"], shell=True, check=True)
    os.rename(".config", "rt-config")
    sb.normal_msg("Successfully modified kernel config.")

sb.normal_msg("Compiling kernel...")
subprocess.run(["genkernel --microcode=all --module-rebuild --kernel-config=/usr/src/linux/rt-config all"], shell=True, check=True)
# splash and plymouth could be added later. See man genkernel.

### SYSTEM CONFIGURATION

sb.normal_msg("Running system configuration tasks...")
subprocess.run(["hostnamectl hostname DecibelLinux"], shell=True, check=True)
subprocess.run(["emerge --quiet --buildpkg --usepkg --ask=n net-misc/dhcpcd"], shell=True, check=True)
subprocess.run(["systemctl enable dhcpcd"], shell=True, check=True)
os.makedirs("/var/db/repos/decibellinux/metadata/", exist_ok=True)
os.makedirs("/usr/lib64/lv2", exist_ok=True) # Force compliance with standard dirs used by other distros.
subprocess.run(["ln -s /usr/lib64/lv2/ /usr/lib/lv2"], shell=True, check=True)

### SYSTEM TOOLS/GRUB CONFIG

sb.normal_msg("Installing system tools...")
subprocess.run(["emerge --quiet --buildpkg --usepkg --ask=n mlocate"], shell=True, check=True)
subprocess.run(["updatedb"], shell=True, check=True) # Populate mlocate db in advance.
subprocess.run(["emerge --quiet --buildpkg --usepkg --ask=n sys-block/io-scheduler-udev-rules"], shell=True, check=True)
subprocess.run(['grub-install --efi-directory=/efi'], shell=True, check=True)
sb.normal_msg("Successfully installed system tools.")

# Enable display manager, if set:
if sb.DISPLAY_MANAGER:
    subprocess.run([f"systemctl enable {sb.DISPLAY_MANAGER}"], shell=True, check=True)

# Copy anything in /efi to a temporary dir, as a vfat partition is mounted on /efi and will be unmounted when exiting chroot.
# This dir will be copied back during user install.

# Noticed 40-realtime-base.conf needs updating, but we already have it where we want.
# Need to automate dispatch-conf with zap-new.

# Exit chroot
sb.normal_msg("Leaving chroot...")
#os.system("exit") # This may be unnecessary.