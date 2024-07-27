# Note: numpy cannot be used. It doesn't exist in a fresh chroot.
from inspect import currentframe
import subprocess
import sys
import re
import requests
import time

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

ARCH_TYPE = "stage3-amd64-desktop-systemd"
DISTFILES_URL = "https://distfiles.gentoo.org/releases/amd64/autobuilds/current-"
BASE_DIR = "/home/audiodef/decibellinux/stagebuilder"
CHROOT_DIR = f"{BASE_DIR}/stage3chroot"
CACHE_DIR = f"{BASE_DIR}/pkgcache" # Store binpkgs for faster builds.
ETC_FILES = True
ETC_FILENAME = "sysfiles.tar.xz"
ETC_URL = f"https://decibellinux.org/src/{ETC_FILENAME}"
SPECIFY_KERNEL = True
KERNEL_TYPE = "gentoo-sources" # The kernel you would type in after an emerge command.
KERNEL_URL = "https://dev.gentoo.org/~mpagano/genpatches/kernels.html"
KERNEL_VER = "6.6.35"
USE_RT_PATCH = True
AUTOFIND_RT_PATCH = True
RT_PATCH_FILE = f"patch-{KERNEL_VER}-rt34.patch.xz"
RT_PATCH_URL = "https://cdn.kernel.org/pub/linux/kernel/projects/rt/6.6/"
RT_PATCHES_BASE_URL = "https://cdn.kernel.org/pub/linux/kernel/projects/rt/"
INSTALL_SOFTWARE = True
DISPLAY_MANAGER="lightdm"
PKG_CACHE = True # Use "buildpkg" and cp files from /var/cache/binpkgs inside chroot to outside chroot.
REMOVE_OLD_SEEDS = False

# def rm_old_seeds(): # Remove old stage3 archives to free up space.

def check_kernel_and_rtpatch_versions():
	# Make sure supplied kernel version is valid:
	manifest_resp = requests.get(KERNEL_URL)
	manifest_resp.raise_for_status()
	has_kernel_ver = None
	for line in manifest_resp.text.splitlines():
		if KERNEL_VER in line:
			has_kernel_ver = line.split()[0]
			break
	if not has_kernel_ver:
		bailout(f"Kernel version {KERNEL_VER} does not exist. Please check {KERNEL_URL} for valid versions.", get_linenum())
	else:
		normal_msg(f"Kernel version {KERNEL_VER} is valid.")
	# Make sure supplied RT patch is valid:
	manifest_resp = requests.get(f"{RT_PATCH_URL}{RT_PATCH_FILE}")
	try:
		manifest_resp.raise_for_status()
		normal_msg(f"RT patch file {RT_PATCH_FILE} is valid.")
	except:
		bailout(f"Could not fetch RT patch {RT_PATCH_FILE} from {RT_PATCH_URL}. Double-check your RT_PATCH_URL and RT_PATCH_FILE to make sure they still exist.", get_linenum())


def autofind_latest_rt_patch():
    # This function also needs to return the URL for the returned patch version.
    normal_msg("Auto-finding latest RT patch vs gentoo-sources compatibility...")
    cleaner = re.compile("<.*?>") # For removing HTML tags later.

    gentoo_sources_page = requests.get(KERNEL_URL)
    gentoo_sources_page.raise_for_status()
    patches_versions = []
    patches_full_versions = []
    rt_patch_filenames = []
    return_items = []

    # Create array of patches versions:
    normal_msg("Fetching RT patches versions, please wait...")
    patches_page_content = requests.get(RT_PATCHES_BASE_URL)
    patches_page_content.raise_for_status()
    stripped_content = re.sub(cleaner, "", patches_page_content.text) # Remove HTML from content.
    for line in stripped_content.splitlines():
        x = False
        x = re.findall(r"[0-9]", line)
        if not line == "":
            if x: # If the line starts with a digit, add the numbers before the slash to an array:
                patches_versions.append(line.split("/")[0]) # We now have an array of all the RT patches version links.

    # Loop through patches_versions to get minor version number (if any):
    patch_name_pattern = re.compile(r'patch-.*?\.patch\.xz') # Current naming convention - check occasionally.
    for x in patches_versions:
        patch_version_page_content = requests.get(f"{RT_PATCHES_BASE_URL}{x}/sha256sums.asc")
        patch_version_page_content.raise_for_status()
        for match in re.findall(patch_name_pattern, patch_version_page_content.text):
            rt_patch_filenames.append(match) # Use to get full URL to download patch.
            patches_full_versions.append(match.split("-rt")[0].removeprefix("patch-"))
    # Create array of gentoo-sources versions:
    normal_msg("Fetching gentoo-sources versions...")
    gentoo_sources_versions = re.findall(r"\d+\.\d+\.+\d+", gentoo_sources_page.text)

    # Find intersection of rt patches and gentoo sources versions.
    res = set(patches_full_versions) & set(gentoo_sources_versions)
    version_list = list(res)
    version_list.sort() # The last item should now be the latest version that matches both the rt patch and gentoo-sources.

    # Return the goods
    return_items.append(version_list[-1]) # 0: The latest version match (version x.y.z).
    return_items.append(version_list[-1][0:3]) # 1: The x.y version only, to be used for the RT patch URL.
    for x in rt_patch_filenames:
        if version_list[-1] in x: # version_list[-1] is our patches-sources match.
            matching_patch = x # (Not sure if more than 1 match is ever a possibility, so keep an eye out.)
    return_items.append(matching_patch) # 2: The full filename of the matching patch so we can download it. 
    return return_items
    #return version_list[-1] # We want only the last element in the array, which is the latest version nmatch.

def umount_all():
    # check should not be True because a non-zero exit status is expected if these filesystems aren't mounted.
    subprocess.run([f"umount --quiet {CHROOT_DIR}/efi"], shell=True)
    subprocess.run([f"umount --quiet -l {CHROOT_DIR}/dev{{/shm,/pts,}}"], shell=True)
    subprocess.run([f"umount --quiet -l {CHROOT_DIR}/sys"], shell=True)
    subprocess.run([f"umount --quiet {CHROOT_DIR}/run"], shell=True)
    subprocess.run([f"umount --quiet {CHROOT_DIR}/proc"], shell=True)

def get_linenum():
    cf = currentframe()
    return cf.f_back.f_lineno

def cache_binpkgs():
	normal_msg("Caching binpkgs...")
	os.makedirs(CACHE_DIR, exist_ok=True)
	copy_tree(f"{CHROOT_DIR}/var/cache/binpkgs", f"{CACHE_DIR}")
	normal_msg("Done.")

def bailout(errmsg, linenum):
    # This could take raise ValueError as an argument.
    # This could cp already built binary packages created by --buildpkg before exiting, so as to shorten the next run even if this one fails.
    print(f"{bcolors.FAIL}!!!!! {time.time()}: {errmsg} Line: {linenum} {bcolors.ENDC}")
    cache_binpkgs()
    sys.exit()

def normal_msg(msg):
    # Can add a starttime = time.time() and subtract time.time() if you want elapsed time instead of current time.
    print(f"{bcolors.OKGREEN}### {time.time()}: {msg} {bcolors.ENDC}")

