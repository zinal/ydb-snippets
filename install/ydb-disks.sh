sudo parted /dev/vdb mklabel gpt -s
sudo parted -a optimal /dev/vdb mkpart primary '0%' '100%'
sudo parted /dev/vdb name 1 ydb_disk_ssd_01
sudo partprobe /dev/vdb

sudo parted /dev/vdc mklabel gpt -s
sudo parted -a optimal /dev/vdc mkpart primary '0%' '100%'
sudo parted /dev/vdc name 1 ydb_disk_ssd_02
sudo partprobe /dev/vdc

sudo parted /dev/vdd mklabel gpt -s
sudo parted -a optimal /dev/vdd mkpart primary '0%' '100%'
sudo parted /dev/vdd name 1 ydb_disk_ssd_03
sudo partprobe /dev/vdd

ls -l /dev/disk/by-partlabel/ydb_disk_ssd_*
