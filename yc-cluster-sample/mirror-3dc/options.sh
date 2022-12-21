
host_gw=gw1
host_base=ycydb

SRCDIR=srcdir.tmp
WORKDIR=YdbWork

keyfile_gw=.ssh/id_ecdsa.pub

yc_zone=ru-central1-b
yc_subnet=default-ru-central1-b
yc_platform=standard-v2
yc_vm_image="image-folder-id=standard-images,image-family=ubuntu-2204-lts"
yc_vm_cores=32
yc_vm_mem=64
yc_data_disk_size=279G

ydb_static=9
ydb_disk_count=1
ydb_config=conf-9n-32c-tls.yaml
ydb_tls=Y
ydb_disk_groups=9

ydbd_mode=tar

# **********************************

if [ -z "$ydbd_mode" ]; then
  ydbd_mode=tar
fi
YDBD_ARCHIVE=ydbd.xz
if [ "$ydbd_mode"=="tar" ]; then
  YDBD_ARCHIVE=ydbd.tar.gz
fi
