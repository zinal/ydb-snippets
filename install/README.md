# YDB 3-node cluster installation

## User and group preparation
```bash
for h in ydb1 ydb2 ydb3; do 
  ssh $h sudo groupadd ydb
  ssh $h sudo useradd ydb -g ydb
  ssh $h sudo usermod -aG disk ydb
done
```

## Working directory setup
```bash
mkdir YdbInstall
cd YdbInstall
```

## Disk preparation
```bash
# Generating ydb-configure-disks script
cat >ydb-configure-disks.sh <<EOF
sudo parted /dev/vdb mklabel gpt -s
sudo parted -a optimal /dev/vdb mkpart primary '0%' '100%'
sudo parted /dev/vdb name 1 ydb_disk_01
sudo partprobe /dev/vdb

sudo parted /dev/vdc mklabel gpt -s
sudo parted -a optimal /dev/vdc mkpart primary '0%' '100%'
sudo parted /dev/vdc name 1 ydb_disk_02
sudo partprobe /dev/vdc

sudo parted /dev/vdd mklabel gpt -s
sudo parted -a optimal /dev/vdd mkpart primary '0%' '100%'
sudo parted /dev/vdd name 1 ydb_disk_03
sudo partprobe /dev/vdd

ls -l /dev/disk/by-partlabel/ydb_disk_*
EOF
```

```bash
# Running disk configuration script
for h in ydb1 ydb2 ydb3; do
  ssh $h mkdir YdbWork
  scp ydb-configure-disks.sh $h:YdbWork/
  ssh $h sudo bash YdbWork/ydb-configure-disks.sh
done
```

## Download and distribute the current binary

```bash
curl -L https://binaries.ydb.tech/ydbd-stable-linux-amd64.tar.gz >ydbd-stable-linux-amd64.tar.gz

# Distribute the binary
for h in ydb1 ydb2 ydb3; do
  ssh $h mkdir ydbd-stable-linux-amd64
  scp ydbd-stable-linux-amd64.tar.gz $h:.
  ssh $h tar xfz ydbd-stable-linux-amd64.tar.gz --strip-component=1 -C ydbd-stable-linux-amd64
done

# Install the binary
for h in ydb1 ydb2 ydb3; do
  ssh $h sudo mkdir -p /opt/ydb/bin /opt/ydb/cfg /opt/ydb/lib
  ssh $h sudo chown -R ydb:ydb /opt/ydb
  ssh $h sudo cp ydbd-stable-linux-amd64/bin/ydbd /opt/ydb/bin/
  ssh $h sudo cp ydbd-stable-linux-amd64/lib/libaio.so /opt/ydb/lib/
  ssh $h sudo cp ydbd-stable-linux-amd64/lib/libiconv.so /opt/ydb/lib/
  ssh $h sudo cp ydbd-stable-linux-amd64/lib/libidn.so /opt/ydb/lib/
done
```

## Disk formatting
```bash
for h in ydb1 ydb2 ydb3; do
  for d in 01 02 03; do
    ssh $h sudo LD_LIBRARY_PATH=/opt/ydb/lib /opt/ydb/bin/ydbd admin bs disk obliterate /dev/disk/by-partlabel/ydb_disk_"$d"
    echo "Status for $h $d: $?"
  done
done
```

## Configuration files distribution
```bash
for h in ydb1 ydb2 ydb3; do
  scp ydb-config.yaml $h:.
  scp ydbd-storage.service $h:.
  scp ydbd-testdb.service $h:.
  ssh $h sudo cp ydb-config.yaml /opt/ydb/cfg/config.yaml
  ssh $h sudo cp ydbd-storage.service /etc/systemd/system/ydbd-storage.service
  ssh $h sudo cp ydbd-testdb.service /etc/systemd/system/ydbd-testdb.service
done
```

or just for the main YDB config file:

```bash
for h in ydb1 ydb2 ydb3; do
  scp ydb-config.yaml $h:.
  ssh $h sudo cp ydb-config.yaml /opt/ydb/cfg/config.yaml
done
```


## Starting the static nodes
```bash
for h in ydb1 ydb2 ydb3; do
  ssh $h sudo systemctl start ydbd-storage
done
for h in ydb1 ydb2 ydb3; do
  ssh $h sudo systemctl status ydbd-storage
done
```

## Storage init and database creation

```bash
# Init blob storage
LD_LIBRARY_PATH=/opt/ydb/lib /opt/ydb/bin/ydbd admin blobstorage config init --yaml-file  /opt/ydb/cfg/config.yaml ; echo $?

# Create the database
LD_LIBRARY_PATH=/opt/ydb/lib /opt/ydb/bin/ydbd admin database /Root/testdb create ROT:1
```

## Starting the dynamic nodes
```bash
for h in ydb1 ydb2 ydb3; do
  ssh $h sudo systemctl start ydbd-testdb
done
for h in ydb1 ydb2 ydb3; do
  ssh $h sudo systemctl status ydbd-testdb
done
```

## Re-configure when needed

```bash
for h in ydb1 ydb2 ydb3; do
  scp ydb-config.yaml $h:.
  ssh $h sudo cp ydb-config.yaml /opt/ydb/cfg/config.yaml
  ssh $h sudo systemctl stop ydbd-storage
  ssh $h sudo systemctl start ydbd-storage
done
```

## Stop all

```bash
for h in ydb1 ydb2 ydb3; do
  ssh $h sudo systemctl stop ydbd-testdb
  ssh $h sudo systemctl stop ydbd-storage
done
```

# YDB 8-node block-4+2 cluster installation

## Install the supporting packages and upgrade the operating system

```bash
for x in `seq 1 8`; do ssh ydb"$x" sudo apt-get install -y screen mc zip unzip atop; done
for x in `seq 1 8`; do ssh ydb"$x" screen -m -d sudo apt-get update; done
for x in `seq 1 8`; do ssh ydb"$x" screen -ls; done
for x in `seq 1 8`; do ssh ydb"$x" screen -m -d sudo apt-get -o Dpkg::Options::='--force-confold' --force-yes -fuy upgrade; done
for x in `seq 1 8`; do ssh ydb"$x" sudo shutdown -r now; done
```
