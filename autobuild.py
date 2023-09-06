#!/usr/bin/env python3

## THIS SCRIPT IS NOT FUNCTIONAL YET. IT WILL BE A REPLACEMENT FOR THE BASH SCRIPT.

import datetime, smtplib, subprocess, sys
from email.message import EmailMessage

url = "https://distfiles.gentoo.org/releases/amd64/autobuilds/"
txtfile = "latest-stage3-amd64-desktop-systemd.txt"
email = "webmaster@gentoostudio.org"
builddir = "/var/tmp/stagebuilder" # Do not use trailing slash here.
seedname = "stage3seed.tar.xz"

def create_mail(subj, msg_body):
	# To keep email credentials out of this script, you need to store them in a file, with this format (without the mailcreds array):
	# smtp.server.tld				(mailcreds[0])
	# port							(mailcreds[1])
	# login_address@domain.tld		(mailcreds[2])
	# login_password				(mailcreds[3])
	# from_address@domain.tld		(mailcreds[4])
	# to_address@domain.tld			(mailcreds[5])
	# Change the file location below to match where you've stored it.
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

def empty_builddir():
	try:
		print("Emptying stage4 build dir...")
		subprocess.run(["rm", "-rf", f"{builddir}/stage4/*"])
		print("Done.")
	except Exception as ex:
		print("Unable to empty out stage4 build dir because: ", ex)
		create_mail("Autobuild failed","Unable to clean out stage4 build dir: %s" % (ex))
	
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

# Download stage3 seed
