#!/bin/bash

OLDDIR="/usr/lib/python2.7/site-packages/euca2ools/commands/ec2"
NEWDIR="euca2ools/commands/ec2"

while read f; do
  echo $f
  oldfile="$OLDDIR/$f"
  newfile="$NEWDIR/$f"
  /bin/cp $oldfile backup
  /bin/cp $newfile $oldfile
done <files_to_deploy.txt
