#!/bin/bash

builddir="/var/tmp/stagebuilder" # Do not use trailing slash here.
echo "Unmounting file systems..."
umount -l $builddir/stage4/dev{/shm,/pts,}
umount -l $builddir/stage4/proc
umount -l $builddir/stage4/sys
umount -l $builddir/stage4/run
echo "Removing stage4 build dir..."
rm -rf $builddir/stage4/
echo "Cleanup complete."
