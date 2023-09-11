#!/usr/bin/env python3

## THIS SCRIPT IS NOT FUNCTIONAL YET. IT WILL BE A REPLACEMENT FOR THE BASH SCRIPT.

### Suggestions for improvement
# Suggested config options:
# * mail_notify: default would be mail_notify=true. mail_notify=false would disable mail notifications.

# Notes to users:
# To keep email credentials out of this script, you need to store them in a file, with this format (without the mailcreds array):
# smtp.server.tld				(mailcreds[0])
# port							(mailcreds[1])
# login_address@domain.tld		(mailcreds[2])
# login_password				(mailcreds[3])
# from_address@domain.tld		(mailcreds[4])
# to_address@domain.tld			(mailcreds[5])
# Change the file location below to match where you've stored it.

import datetime, os, shutil, smtplib, subprocess, sys, urllib.request
from email.message import EmailMessage
from pathlib import Path

# Variables and data prep
stagebuilder = {}	# Object for storing values from /etc/conf.d/stagebuilder.
with open("/etc/conf.d/stagebuilder") as f:
	for line in f.readlines():
		key, value = line.rstrip("\n").split("=")
		stagebuilder[key] = value
url = "https://distfiles.gentoo.org/releases/amd64/autobuilds/"	# URL where Gentoo stage3 builds are kept.
txtfile = f"latest-stage3-{stagebuilder["release_type"]}.txt"	# File from which to parse the filename of the latest build.
stage4dir = Path(f"{stagebuilder["builddir"]}/stage4")
print("Stage4 dir already exists.") if stage4dir.is_dir() else os.mkdir(f"{stagebuilder["builddir"]}/stage4") # Make sure this dir exists.
seedname = "stage3seed.tar.xz"	# Filename to store the seed as.

def show_progress(block_num, block_size, total_size):
	percent_done = round(block_num * block_size / total_size *100,2)
	print(f"{percent_done}%", end="\r")

def create_mail(subj, msg_body):
	# Change mail_notify in /etc/conf.d/stagebuilder to turn mail notifications on/off.
	if stagebuilder["mail_notify"]:
		try: 
			print("Sending mail for: %s" % subj)
			msg = EmailMessage()
			msg.set_content(msg_body)
			msg['Subject'] = subj
			msg['From'] = stagebuilder["smtp_from"]
			msg['To'] = stagebuilder["smtp_to"]
			smtp = smtplib.SMTP(stagebuilder["smtp_host"], stagebuilder["smtp_port"])
			smtp.starttls() 
			smtp.login(stagebuilder["smtp_login"],stagebuilder["smtp_pass"])
			smtp.send_message(msg)
			smtp.quit() 
			print ("Mail sent successfully.") 
		except Exception as ex: 
			print("Unable to send mail: ", ex)
			print("Exiting autobuild. Goodbye.")
			sys.exit(0)

def unmount_all():
	try:
		print("Unmounting dev, proc, sys, and run...")
		subprocess.run(["umount", "-l", f"{stagebuilder["builddir"]}/stage4/dev{{/shm,/pts,}}"])
		subprocess.run(["umount", "-l", f"{stagebuilder["builddir"]}/stage4/proc"])
		subprocess.run(["umount", "-l", f"{stagebuilder["builddir"]}/stage4/sys"])
		subprocess.run(["umount", "-l", f"{stagebuilder["builddir"]}/stage4/run"])
		# Assuming that a "No such file" means the dir isn't mounted, which is what we want.
		print("Done.")
	except Exception as ex:
		print("Unable to successfully umount all because: ", ex)
		create_mail("Autobuild failed","Unable to successfully unmount all: %s" % (ex))
		print("Exiting autobuild. Goodbye.")
		sys.exit(0)

def empty_builddir():
	try:
		print("Emptying stage4 build dir...")
		shutil.rmtree(f"{stagebuilder["builddir"]}/stage4") # Rm it
		os.mkdir(f"{stagebuilder["builddir"]}/stage4") # Restore empty dir
		print("Done.")
	except Exception as ex:
		print("Unable to empty out stage4 build dir because: ", ex)
		create_mail("Autobuild failed","Unable to clean out stage4 build dir: %s" % (ex))
		print("Exiting autobuild. Goodbye.")
		sys.exit(0)

def handle_failed_fetch(e, attempted_url):
	print("Could not download seed: ", e)
	print(f"The file I attempted to retrieve was: {attempted_url}")
	print("Please check for typos.")
	create_mail("Autobuild failed",f"Unable to fetch seed at {attempted_url} because: %s" % e)
	# No point in continuing if this failed.
	print("Exiting autobuild. Goodbye.")
	sys.exit(0)

# Prompt to make sure binpkgs from previous run have been taken care of.
binpkgcheck = input("Binpkgs will be rebuilt. Did you handle the previous run? Enter 'n' to exit, anything else to continue: ")
if binpkgcheck == 'n':
	print("Handle the binpkgs and re-run this script when ready. Goodbye.")
	sys.exit(0)

# Notify that build is starting.
now = datetime.datetime.now()
create_mail("Starting autobuild","The latest build was started at %s" % (now))

# Cleanup before beginning build.
unmount_all()
empty_builddir()

# Downloading stage3 seed
try:
	# Get text file describing latest stage3 tarball.
	print("Fetching latest.txt...")
	urllib.request.urlretrieve(f"{url}{txtfile}", "latest.txt", show_progress)
	print("Done.")
except Exception as ex:
	handle_failed_fetch(ex, f"{url}{txtfile}")
# Get the last line from this file, which contains the seed URL we need.
latest = subprocess.run(
	["tail", "-1", "latest.txt"],
	capture_output = True,
	text = True
)
# Cut everything after the first space in this line of text to get the URL we need:
fetch_seed = latest.stdout[:latest.stdout.index(" ")]
try:
	# Fetch actual seed:
	print("Fetching seed, please wait...") # In the future, a progress indicator might be nice.
	urllib.request.urlretrieve(f"{url}{fetch_seed}", seedname, show_progress)
	print("Done.")
except Exception as ex:
	handle_failed_fetch(ex, f"{url}{fetch_seed}")
try:
	# Move seed to build dir:
	print("Moving seed file to build dir...")
	mvseed = subprocess.run(
		["mv", f"{seedname}", f"{stagebuilder["builddir"]}/"],
		capture_output = True,
		text = True
	)
	if "cannot stat " in mvseed.stderr:
		# This is not handled as an exception, so we do this here:
		print("Unable to move seed to build dir: ", mvseed.stderr)
		create_mail("Autobuild failed","Unable to move seed to build dir: %s" % mvseed.stderr)
		print("Exiting autobuild. Goodbye.")
		sys.exit(0)
	else:
		print("Done.")
		try:
			print("Removing latest.txt...")
			os.remove("latest.txt") # Once the seed has been downloaded and moved, this file is no longer needed.
			print("Done.")
		except Exception as ex:
			print("Could not remove latest.txt: ", ex) # No need to exit here. This is not a big deal.
except Exception as ex:
	print("Unable to move seed to build dir: ", ex)
	create_mail("Autobuild failed","Unable to move seed to build dir: %s" % ex)
	print("Exiting autobuild. Goodbye.")
	sys.exit(0)

# Unpack the seed
try:
	# Would be nice if this could be done in a Pythonish way.
	# Also would be nice to have a progress indicator a la show_progress as defined earlier.
	print("Unpacking seed, please wait...")
	subprocess.run(["tar", "xpf", f"{stagebuilder["builddir"]}/{seedname}", "--xattrs-include='*.*'", "--numeric-owner", "-C", f"{stagebuilder["builddir"]}/stage4"])
	print("Done.")
except Exception as ex:
	print("Could not unpack seed: ", ex)
	create_mail("Autobuild failed","Could not unpack seed: %s" % ex)
	print("Exiting autobuild. Goodbye.")
	sys.exit(0)

# Setting up and entering chroot
try:
	print("Mounting filesystems...")
	subprocess.run(["mount", "-t", "proc", "/proc", f"{stagebuilder["builddir"]}/stage4/proc"])
	subprocess.run(["mount", "--rbind", "/sys", f"{stagebuilder["builddir"]}/stage4/sys"])
	subprocess.run(["mount", "--rbind", "/dev", f"{stagebuilder["builddir"]}/stage4/dev"])
	subprocess.run(["mount", "--make-rslave", f"{stagebuilder["builddir"]}/stage4/sys"])
	subprocess.run(["mount", "--make-rslave", f"{stagebuilder["builddir"]}/stage4/dev"])
	subprocess.run(["mount", "--bind", "/run", f"{stagebuilder["builddir"]}/stage4/run"])
	subprocess.run(["mount", "--make-slave", f"{stagebuilder["builddir"]}/stage4/run"])
	print("Done.")
except Exception as ex:
	print("Could not mount filesystems: ", ex)
	create_mail("Autobuild failed","Could not mount filesystems: %s" % ex)
	print("Exiting autobuild. Goodbye.")
	sys.exit(0)
	
subprocess.run(["cp", "/etc/resolv.conf", f"{stagebuilder["builddir"]}/stage4/etc/"])
#cp chroot_autobuild.sh $builddir/stage4/ || die "Could not cp chroot_autobuild.sh to chroot."
#cp std-pkg.list $builddir/stage4/ || die "Could not cp the packages file to chroot."
#chroot $builddir/stage4 ./chroot_autobuild.sh

# Cleanup
unmount_all()
