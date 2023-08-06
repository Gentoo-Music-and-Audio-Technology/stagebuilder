#!/bin/bash

# Use this script if you need to force autobuild to quit before it's done,
# or if autobuild exits unexpectedly.

builddir="/var/tmp/stagebuilder" # Do not use trailing slash here.
echo "Unmounting file systems..."
if [ "$(ls -A $builddir/stage4/dev)" ]; then umount -l $builddir/stage4/dev{/shm,/pts,}; fi
if [ "$(ls -A $builddir/stage4/proc)" ]; then umount -l $builddir/stage4/proc; fi
if [ "$(ls -A $builddir/stage4/sys)" ]; then umount -l $builddir/stage4/sys; fi
if [ "$(ls -A $builddir/stage4/run)" ]; then umount -l $builddir/stage4/run; fi
echo "Removing stage4 build dir..."
if [ "$(ls -A $builddir/stage4/)" ]; then rm -rf $builddir/stage4/*; fi
echo "Done."
echo "Removing binpkg dir..."
rm -rf $builddir/binpkgs/*
echo "Done."
echo "Cleanup complete."
