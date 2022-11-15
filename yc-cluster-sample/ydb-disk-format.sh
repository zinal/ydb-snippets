#! /bin/sh

disk=/dev/vdb
label=ydb_disk_01

parted ${disk} mklabel gpt -s
parted -a optimal ${disk} mkpart primary '0%' '100%'
parted ${disk} name 1 ${label}
partprobe ${disk}

/opt/ydb/bin/ydbd admin bs disk obliterate /dev/disk/by-partlabel/${label}
ST=$?
echo "Status for ${disk} -> ${label} at "`hostname`": ${ST}"
