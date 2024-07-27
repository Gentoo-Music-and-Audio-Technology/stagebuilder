#!/usr/bin/env python

import requests
import os
import shutil
import tarfile
import subprocess
import stagebuilder_class as sb
from pathlib import Path
from distutils.dir_util import copy_tree

'''
TODO:
1. Logging.
2. Email/txt notification on build complete.
'''

### SANITY CHECKS:

if os.geteuid() != 0:
	sb.bailout("This program must be run as root. Exiting now.", sb.get_linenum())
if sb.AUTOFIND_RT_PATCH:
	sb.normal_msg("Autofinding latest realtime patch this run.")
else:
	sb.check_kernel_and_rtpatch_versions()

### DOWNLOAD STAGE3

# Get current stage3 filename:
arch_url = f"{sb.DISTFILES_URL}{sb.ARCH_TYPE}/"
manifest_resp = requests.get(f"{arch_url}latest-{sb.ARCH_TYPE}.txt") # Get the manifest file.
manifest_resp.raise_for_status() # Halt execution if the URL for the manifest file is not valid.
xz_filename = None
for line in manifest_resp.text.splitlines():
    if line.startswith(sb.ARCH_TYPE) and ".tar.xz" in line: # Change this logic if the manifest file format changes.
        xz_filename = line.split()[0] # Extract the current stage3 filename from the manifest file.
        break
if not xz_filename:
    raise ValueError("Could not get the stage3 filename.")
else:
	sb.normal_msg(f"Current stage3 is {xz_filename}.")

# Fetch stage3 seed file or continue with existing seed if it is still current:
seed_file_path = Path(xz_filename)
if seed_file_path.exists():
	sb.normal_msg("We already have that file. Proceeding.")
else:
	sb.normal_msg("No local copy exists. Fetching...")
	response = requests.get(f"{arch_url}/{xz_filename}", stream=True)
	response.raise_for_status() # Make sure the URL is valid and/or there is a working connection.
	with open(xz_filename, mode="wb") as file:
		for chunk in response.iter_content(chunk_size=10 * 1024):
			file.write(chunk)
	sb.normal_msg("Done.")

### UNPACK STAGE3 SEED

sb.normal_msg("Clearing previous run...")
try:
	sb.umount_all()
	shutil.rmtree(sb.CHROOT_DIR, ignore_errors=True) # Clear previous run. Any errors would be because this path doesn't exist yet, and that's fine.
	os.makedirs(sb.CHROOT_DIR, exist_ok=False) # Create empty chroot dir. exist_ok should not be True because it should have been rm'd by previous line.
	sb.normal_msg("Done.")
except:
	sb.umount_all()
	raise ValueError("Faild to clear previous run.")
	#sb.bailout("Failed to clear previous run.", sb.get_linenum())
sb.normal_msg("Extracting stage3. This could take a few moments...")
try:
	with tarfile.open(f'{xz_filename}') as f:
		f.extractall(f'{sb.CHROOT_DIR}')
		# Use subprocess if it turns out --xattrs-include='*.*' --numeric-owner is essential to this step.
	sb.normal_msg("Done.")
except:
	sb.umount_all()
	sb.bailout("Failed to extract stage3 seed archive.", sb.get_linenum())

### CHROOTING

sb.normal_msg("Copying resolv.conf...")
try:
	shutil.copy('/etc/resolv.conf', f'{sb.CHROOT_DIR}/etc/resolv.conf') # Ensure network access inside chroot.
	sb.normal_msg("Done.")
except:
	sb.umount_all()
	sb.bailout("Failed to copy resolv.conf.", sb.get_linenum())

# Cp /etc/portage and other files into unpacked stage3.
# Do this now because linux-firmware requires ACCEPT_LICENSE. Might as well do it all in one go.
if sb.ETC_FILES:
	# Because files within the system files archive may have changed, we will not check for an extant archive locally.
	sb.normal_msg("Fetching system files...")
	response = requests.get(sb.ETC_URL, stream=True)
	response.raise_for_status() # Make sure the URL is valid and/or there is a working connection.
	with open(sb.ETC_FILENAME, mode="wb") as file:
		for chunk in response.iter_content(chunk_size=10 * 1024):
			file.write(chunk)
	sb.normal_msg("Done.")
	sb.normal_msg("Extracting system files...")
	with tarfile.open(f'{sb.ETC_FILENAME}') as f:
		f.extractall(f'{sb.CHROOT_DIR}')
	sb.normal_msg("Done.")
else:
	sb.normal_msg("No extra system files specified. Proceeding.")

# Mount filesystems:
sb.normal_msg("Mounting filesystems for chrooting...")
try:
	subprocess.run([f"mount --types proc /proc {sb.CHROOT_DIR}/proc"], shell=True, check=True)
	subprocess.run([f"mount --rbind /sys {sb.CHROOT_DIR}/sys"], shell=True, check=True)
	subprocess.run([f"mount --make-rslave {sb.CHROOT_DIR}/sys"], shell=True, check=True)
	subprocess.run([f"mount --rbind /dev {sb.CHROOT_DIR}/dev"], shell=True, check=True)
	subprocess.run([f"mount --make-rslave {sb.CHROOT_DIR}/dev"], shell=True, check=True)
	subprocess.run([f"mount --bind /run {sb.CHROOT_DIR}/run"], shell=True, check=True)
	subprocess.run([f"mount --make-slave {sb.CHROOT_DIR}/run"], shell=True, check=True)
	sb.normal_msg("Done.")
except: # Even with check=True, we need a try/except here so we can run unmount_all().
	sb.umount_all()
	sb.bailout("Failed to mount required filesystems for chrooting.", sb.get_linenum())

# Enter chroot
if sb.PKG_CACHE:
	if os.path.isdir(sb.CACHE_DIR): # Restore cache only if it exists.
		sb.normal_msg("Restoring binpkg cache...")
		os.makedirs(f"{sb.CHROOT_DIR}/var/cache/binpkgs", exist_ok=True)
		copy_tree(sb.CACHE_DIR, f"{sb.CHROOT_DIR}/var/cache/binpkgs")
		sb.normal_msg("Done.")
	else: # Otherwise, it will be built during this run.
		sb.normal_msg("No cache exists yet. Proceeding without.")

sb.normal_msg("Entering chroot...")
try:
	shutil.copy('stagebuilder_chroot.py', f'{sb.CHROOT_DIR}') # Cp chroot program to chroot.
	shutil.copy('stagebuilder_class.py', f'{sb.CHROOT_DIR}') # Cp class file to chroot.
	if sb.INSTALL_SOFTWARE:
		shutil.copy('stagebuilder_pkgs', f'{sb.CHROOT_DIR}') # Cp pkgs file to chroot.
	subprocess.run([f"chmod +x {sb.CHROOT_DIR}/stagebuilder_chroot.py"], shell=True, check=True)
	# Chroot and let the chroot program take over.
	# An "if SPECIFY_KERNEL" would go here.
	subprocess.run([f"chroot {sb.CHROOT_DIR} ./stagebuilder_chroot.py"], shell=True, check=True)
except:
	sb.umount_all()
	raise ValueError("Failed to enter chroot.")
	#sb.bailout("Failed to enter chroot.", sb.get_linenum())

### CACHE BACKUP
# This section could also update the Decibel Linux binary repo if/when it is established.

if sb.PKG_CACHE: # If caching binpkgs to speed up build time.
	sb.cache_binpkgs()

### PACKING UP

sb.normal_msg("Control returned from chroot.")
sb.normal_msg("Unmounting chroot...")
# CHROOT_DIR will not be rm'd so 1. It can be packed up for distribution and 2. User can poke around in it before the next run if troubleshooting is needed.
# Stage3 seed will not be rm'd so it can be reused if there isn't a new one yet.
# But you'll have to stay on top of clearing out old stage3's.
sb.umount_all()

# We will need a notification system, such as sending an email when the job is done.
# An automated mv to a www dir might also be helpful.
# Such an automated mv should also backup the previous tarball.
# Ideally, there would be an automated test install on a VM as well.
# Bash version produced an app list to be published on the site. Be nice to do that here as well.
sb.normal_msg("Packing up...")
# The excludes appear to not be working at all, though the tar command executes successfully. 
# So we have a 5.3 GB file that should be about 3.4. 
# Would also be nice to have a --quiet option if one exists.
excludes = f"--exclude='{sb.CHROOT_DIR}/sys/' \
	--exclude='{sb.CHROOT_DIR}/dev/' \
	--exclude='{sb.CHROOT_DIR}/proc/' \
	--exclude='{sb.CHROOT_DIR}/stagebuilder*' \
	--exclude='{sb.CHROOT_DIR}/var/cache/distfiles/' \
	--exclude='{sb.CHROOT_DIR}/var/db/repos/' \
	--exclude='{sb.CHROOT_DIR}/__pycache__' \
	--exclude='{sb.CHROOT_DIR}/usr/src/linux-*' \
	--exclude='{sb.CHROOT_DIR}/var/cache/binpkgs/'"
tar_cmd = f"tar {excludes} -Jvcf {sb.BASE_DIR}/decibellinux-latest.tar.xz -C {sb.CHROOT_DIR} ."
# The J has to be the first option after the dash or the tar command will fail. Jesus fucking Christ.
sb.normal_msg(f"Running command {tar_cmd}")
sb.normal_msg("This will take a significant amount of time.")
subprocess.run([tar_cmd], shell=True, check=True)

sb.normal_msg("Build complete.")