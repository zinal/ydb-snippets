
host_gw=gw1
host_base=ycydb

SRCDIR=srcdir.tmp
WORKDIR=YdbWork

keyfile_gw=.ssh/id_ecdsa.pub

yc_zone=ru-central1-b
yc_subnet=default-ru-central1-b
yc_platform=standard-v3
yc_vm_image="image-folder-id=standard-images,image-family=ubuntu-2204-lts"
yc_vm_cores=16
yc_vm_mem=32

ydb_static=3
ydb_disk_count=3
ydb_config=conf-3n-16c.yaml
