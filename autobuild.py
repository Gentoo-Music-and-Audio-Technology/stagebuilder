#!/usr/bin/env python3

## THIS SCRIPT IS NOT FUNCTIONAL YET. IT WILL BE A REPLACEMENT FOR THE BASH SCRIPT.

### Suggestions for improvement
# Suggested config options:
# * mail_notify: default would be mail_notify=true. mail_notify=false would disable mail notifications.
# Other suggestions:
# * create_mail() mailcreds file should be incorporated into a larger config file with item=value pairs.

# Notes to users:
# To keep email credentials out of this script, you need to store them in a file, with this format (without the mailcreds array):
# smtp.server.tld				(mailcreds[0])
# port							(mailcreds[1])
# login_address@domain.tld		(mailcreds[2])
# login_password				(mailcreds[3])
# from_address@domain.tld		(mailcreds[4])
# to_address@domain.tld			(mailcreds[5])
# Change the file location below to match where you've stored it.

import datetime, smtplib, subprocess, sys, urllib.request
from email.message import EmailMessage

# Variables and basic setup
url = "https://distfiles.gentoo.org/releases/amd64/autobuilds/"
txtfile = "latest-stage3-amd64-desktop-systemd.txt"
email = "webmaster@gentoostudio.org"
builddir = "/var/tmp/stagebuilder" # Do not use trailing slash here.
subprocess.run(["mkdir", "-p", f"{builddir}"]) # Make sure this dir exists
seedname = "stage3seed.tar.xz"

def create_mail(subj, msg_body):
	with open("/home/audiodef/autobuild_email") as fi:
		mailcreds = fi.read().split('\n')
	try: 
		print("Sending mail for: %s" % (subj))
		msg = EmailMessage()
		msg.set_content(msg_body)
		msg['Subject'] = subj
		msg['From'] = mailcreds[4]
		msg['To'] = mailcreds[5]
		smtp = smtplib.SMTP(mailcreds[0], mailcreds[1]) 
		smtp.starttls() 
		smtp.login(mailcreds[2],mailcreds[3])
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
		subprocess.run(["umount", "-l", f"{builddir}/stage4/dev{{/shm,/pts,}}"])
		subprocess.run(["umount", "-l", f"{builddir}/stage4/proc"])
		subprocess.run(["umount", "-l", f"{builddir}/stage4/sys"])
		subprocess.run(["umount", "-l", f"{builddir}/stage4/run"])
		# Assuming that a "No such file" means the dir isn't mounted, which is what we want.
		print("Done.")
	except Exception as ex:
		print("Unable to successfully umount all because: ", ex)
		create_mail("Autobuild failed","Unable to successfully unmount all: %s" % (ex))
		print("Exiting autobuild. Goodbye.")
		sys.exit(0)

def empty_builddir():
	# Rm leftover stuff from previous run
	try:
		subprocess.run(["rm", f"{seedname}"])
		subprocess.run(["rm", "latest.txt"])
	except Exception as ex:
		print("Unable to remove leftover files: ", ex)
		create_mail("Autobuild failed","Unable to remove leftover files: %s" % ex)
		print("Exiting autobuild. Goodbye.")
		sys.exit(0)
	try:
		print("Emptying stage4 build dir...")
		subprocess.run(["rm", "-rf", f"{builddir}/stage4/*"])
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
	urllib.request.urlretrieve(f"{url}{txtfile}", filename="latest.txt")
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
	urllib.request.urlretrieve(f"{url}{fetch_seed}", filename=seedname)
	print("Done.")
except Exception as ex:
	handle_failed_fetch(ex, f"{url}{fetch_seed}")
try:
	# Move seed to build dir:
	mvseed = subprocess.run(
		["mv", f"{seedname}", f"{builddir}/"],
		capture_output = True,
		text = True
	)
	if "cannot stat " in mvseed.stderr:
		# This is not handled as an exception, so we do this here:
		print("Unable to move seed to build dir: ", mvseed.stderr)
		create_mail("Autobuild failed","Unable to move seed to build dir: %s" % mvseed.stderr)
		print("Exiting autobuild. Goodbye.")
		sys.exit(0)
except Exception as ex:
	print("Unable to move seed to build dir: ", ex)
	create_mail("Autobuild failed","Unable to move seed to build dir: %s" % ex)
	print("Exiting autobuild. Goodbye.")
	sys.exit(0)
