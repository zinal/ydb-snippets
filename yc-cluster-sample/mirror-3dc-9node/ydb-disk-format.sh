#! /bin/sh

xn=0
for xl in b; do

xn=`echo "$xn + 1" | bc`
disk=/dev/vd${xl}
label=ydb_disk_${xn}

parted ${disk} mklabel gpt -s
parted -a optimal ${disk} mkpart primary '0%' '100%'
parted ${disk} name 1 ${label}
partprobe ${disk}

/opt/ydb/bin/ydbd admin bs disk obliterate /dev/disk/by-partlabel/${label}
ST=$?
echo "Status for ${disk} -> ${label} at "`hostname`": ${ST}"

done
