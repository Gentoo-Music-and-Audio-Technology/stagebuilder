#!/usr/bin/env python3

## THIS SCRIPT IS NOT FUNCTIONAL YET. IT WILL BE A REPLACEMENT FOR THE BASH SCRIPT.

import datetime, smtplib, sys
from email.message import EmailMessage

def create_mail(subj, msg_body):
	# To keep email credentials out of this script, you need to store them in a file, with this format:
	# smtp.server.tld
	# port
	# login_address@domain.tld
	# login_password
	# from_address@domain.tld
	# to_address@domain.tld
	# Access these values in the mailcreds array: mailcreds[0] through mailcreds[5]
	# Change the file location below to match where you've stored it.
	with open("/home/audiodef/autobuild_email") as fi:
		mailcreds = fi.read().split('\n')
	try: 
		msg = EmailMessage()
		msg.set_content(msg_body)
		msg['Subject'] = subj
		msg['From'] = mailcreds[4]
		msg['To'] = mailcreds[5]
		msg['Date'] = now
		smtp = smtplib.SMTP(mailcreds[0], mailcreds[1]) 
		smtp.starttls() 
		smtp.login(mailcreds[2],mailcreds[3])
		smtp.send_message(msg)
		smtp.quit() 
		print ("Mail sent successfully.") 
	except Exception as ex: 
		print("Unable to send mail: ", ex)
	
url = "https://distfiles.gentoo.org/releases/amd64/autobuilds/"
txtfile = "latest-stage3-amd64-desktop-systemd.txt"
email = "webmaster@gentoostudio.org"
builddir = "/var/tmp/stagebuilder" # Do not use trailing slash here.
seedname = "stage3seed.tar.xz"

# Prompt to make sure binpkgs from previous run have been taken care of.
binpkgcheck = input("Binpkgs will be rebuilt. Did you handle the previous run? Enter 'n' to exit, anything else to continue: ")
if binpkgcheck == 'n':
	print("Handle the binpkgs and re-run this script when ready. Goodbye.")
	sys.exit(0)

now = datetime.datetime.now()
create_mail("Starting autobuild","The latest build was started at %s" % (now))
