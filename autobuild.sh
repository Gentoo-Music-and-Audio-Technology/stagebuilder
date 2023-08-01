#!/bin/bash

# Download a stage3 seed
# Unpack it
# Chroot into it
# chroot_autobuild.sh runs in chroot
# Make tarball
# scp tarball to VM's host
# If build successful, make a backup of seed tarball

### Command-line arguments (only one can be used at a time)
# noseed: Do not download and update the seed. Used when something has changed and throws a wrench into catalyst builds. In this case, cp the last known good seed instead.

### Note that full paths must be used, including to symlinks, so that the cronjob that calls this script (if used) won't fail.

set -eo # Stop at first error (o catches piped errors)

url="https://distfiles.gentoo.org/releases/amd64/autobuilds/"
txtfile="latest-stage3-amd64-desktop-systemd.txt"
email="webmaster@gentoostudio.org"
builddir="/var/tmp/stagebuilder" # Do not use trailing slash here.
seedname="stage3seed.tar.xz"

# Usage: create_mailmsg "Subject" "message_body"
create_mailmsg(){
        echo -e "Subject: $1" > mail_msg
        echo -e "\n" >> mail_msg
        echo -e "$2" >> mail_msg
        ssmtp -v $email < mail_msg
        echo "Mail sent to $email because: $2"
        rm mail_msg
}

unmount_all(){
	echo "Unmounting dev, proc, sys, and run..."
	umount -l $builddir/stage4/dev{/shm,/pts,}
	umount -l $builddir/stage4/proc
	umount -l $builddir/stage4/sys
	umount -l $builddir/stage4/run
	echo "Done."
}

cleanup(){
	echo "Emptying stage4 directory..."
	rm -rf $builddir/stage4/*
	echo "Cleanup complete."
}

exit_gracefully(){
	echo "Error: ($1) occured at line $2"
	unmount_all
	cleanup
	create_mailmsg "Autobuild error" "Error: ($1) occured at line $2"
	echo "Exiting autobuild."
}

trap 'exit_gracefully $? $LINENO' ERR

# Notify that build is starting
start_time=$(date)
create_mailmsg "Build beginning" "The latest build was started at $start_time."

### DOWNLOAD SEED
# Get text file describing latest stage3 tarball.
# -O option circumvents wget creating a new file on every run and gives us a fixed filename to use.
# The wget -S option is --server-response, which can be grepped.
# mail-mta/ssmtp has been installed and ssmtp.conf has been configured.
if [[ $1 != "noseed" ]]; then # No argument passed to skip downloading a seed
	if [[ `wget -S --spider $url$txtfile 2>&1 | grep 'HTTP/1.1 200 OK'` ]];
		then wget -O latest.txt $url$txtfile;
		else
			create_mailmsg "wget failed (text file)" "wget failed to fetch text file at: $url$txtfile"
			exit 1;
	fi
	# Parse text file for URL
	# Use tail cmd to read last line of file, which is all we need,
	# then use sed to chop off everything after the space in that line
	# When wget is done, move the file to where its needed
	# Not sure we need an ifelse here. If the above check passes, this wget should work.
	latest=$(tail -n 1 latest.txt | sed 's#[[:space:]].*##')
	wget -O $seedname $url$latest
	if [ $? != 0 ]; then
		create_mailmsg "wget failed to fetch seed" "wget failed to fetch seed at: $url$latest"
		exit 1;
	fi
	# Trailing slash prevents mv'ing seed to a new file.
	mkdir -p $builddir	# Because apparently we need to do this
	cp $seedname $builddir/
	if [ $? != 0 ]; then
		# Not sure why this would fail, except for hardware issues, but just in case...
		create_mailmsg "Failed to mv seed" "Seed file could not be moved to build dir."
		exit 1;
	fi
	else
		echo "Not fetching new seed. Copying last known seed instead."
		cp $builddir/stage3seed_lastworking.tar.xz $builddir/$seedname
fi

### UNPACK SEED

mkdir -p $builddir/stage4
echo "Unpacking seed... Please be patient."
tar xpf $builddir/$seedname --xattrs-include='*.*' --numeric-owner -C $builddir/stage4 # Verbose to troubleshoot

### PART 3: CHROOT

mount -t proc /proc $builddir/stage4/proc
mount --rbind /sys $builddir/stage4/sys
mount --rbind /dev $builddir/stage4/dev
mount --make-rslave $builddir/stage4/sys
mount --make-rslave $builddir/stage4/dev
mount --bind /run $builddir/stage4/run
mount --make-slave $builddir/stage4/run

cp /etc/resolv.conf $builddir/stage4/etc/
cp chroot_autobuild.sh $builddir/stage4/
chroot $builddir/stage4 ./chroot_autobuild.sh

# Mv binpkgs out of stage4. Don't forget to scp to web server on VM host.
# Need to ls recursively to get pkgs added.
#date >> $builddir/binpkgs_added
#ls -lh $builddir/stage4/var/cache/binpkgs/ >> $builddir/binpkgs_added # Stay updated on what's been added this run
#echo "\n\n" >> $builddir/binpkgs_added # Make sure next run starts on new line (echo "\n" doesn't seem to work...)
rm -rf $builddir/binpkgs # Clear out binpkgs from previous build
mv $builddir/stage4/var/cache/binpkgs/ $builddir/

# Pack up stage4 and empty out stage4 dir.
unmount_all
cd $builddir/stage4
echo "Packing up stage4... Please be patient."
rm $builddir/stage4/chroot_autobuild.sh
tar -cjf $builddir/decibellinux-stage4.tar.bz2 --exclude='/run/*' --exclude='/dev/*' --exclude='/sys/*' --exclude='/proc/*' .
cleanup

end_time=$(date)
create_mailmsg "decibel Linux build complete" "The latest build was completed at $end_time."
