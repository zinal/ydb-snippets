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
# Generating ydb-disks script
cat >ydb-disks.sh <<EOF
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
  scp ydb-disks.sh $h:YdbWork/
  ssh $h sudo bash YdbWork/ydb-disks.sh
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

## 0. Install the supporting packages and upgrade the operating system

```bash
for x in `seq 1 8`; do ssh ydb"$x" sudo apt-get install -y screen mc zip unzip atop; done
for x in `seq 1 8`; do ssh ydb"$x" screen -m -d sudo apt-get update; done
for x in `seq 1 8`; do ssh ydb"$x" screen -ls; done
for x in `seq 1 8`; do ssh ydb"$x" screen -m -d sudo apt-get -o Dpkg::Options::='--force-confold' --force-yes -fuy upgrade; done
for x in `seq 1 8`; do ssh ydb"$x" sudo shutdown -r now; done
```

## 0. YC-specific VM preparation

```bash
# Configure hosts, reboot required
for  x in `seq 1 8`; do h=ydb"$x"
  scp /etc/cloud/templates/hosts.debian.tmpl "$h":.
  ssh "$h" sudo cp hosts.debian.tmpl /etc/cloud/templates/hosts.debian.tmpl
done
```

```bash
# Login to YC
yc iam create-token >/dev/null
# Creating the disks
for x in 1 2 3 4 5 6 7 8; do for y in 1 2; do
  yc compute disk create --name ydb"$x"disk"$y" --zone ru-central1-b --size 93G --type network-ssd-nonreplicated --async
done; done
# Attaching the disks
for x in 1 2 3 4 5 6 7 8; do for y in 1 2; do
  yc compute instance attach-disk --name ydb"$x" --disk-name ydb"$x"disk"$y" --auto-delete --async
done; done
```

## 1. User and group preparation

```bash
# Create ydb user and group
for  x in `seq 1 8`; do h=ydb"$x"
  ssh $h sudo groupadd ydb
  ssh $h sudo useradd ydb -g ydb
  ssh $h sudo usermod -aG disk ydb
done
# Validate ydb user identity
for  x in `seq 1 8`; do h=ydb"$x"
  ssh $h sudo id ydb
done
```

## 2. Download and install the current binary

```bash
# Create the working dir on the bootstrap node
[-d YdbInstall] || mkdir YdbInstall
cd YdbInstall
# Download the binary
YDB_DITTO=ydbd-22.4.30-linux-amd64.tar.gz
wget https://binaries.ydb.tech/release/22.4.30/$YDB_DITTO
# Upload and unpack the binary to cluster nodes
for  x in `seq 1 8`; do h=ydb"$x"
  ssh $h rm -rf YdbWork
  ssh $h mkdir -pv YdbWork/code
  scp $YDB_DITTO "$h":YdbWork/
  ssh $h tar xfz YdbWork/$YDB_DITTO --strip-component=1 -C YdbWork/code
done
# Create the destination directories and install the binary
for  x in `seq 1 8`; do h=ydb"$x"
  ssh $h sudo rm -rf /opt/ydb
  ssh $h sudo mkdir -p /opt/ydb/bin /opt/ydb/cfg /opt/ydb/lib
  ssh $h sudo chown -R ydb:ydb /opt/ydb
  ssh $h sudo cp -fv YdbWork/code/bin/ydbd /opt/ydb/bin/
  ssh $h sudo cp -fv YdbWork/code/lib/lib\* /opt/ydb/lib/
done
```

## 3. Disk preparation
```bash
# Generating ydb-disks script
cat >ydb-disks.sh <<EOF
sudo parted /dev/vdb mklabel gpt -s
sudo parted -a optimal /dev/vdb mkpart primary '0%' '100%'
sudo parted /dev/vdb name 1 ydb_disk_01
sudo partprobe /dev/vdb

sudo parted /dev/vdc mklabel gpt -s
sudo parted -a optimal /dev/vdc mkpart primary '0%' '100%'
sudo parted /dev/vdc name 1 ydb_disk_02
sudo partprobe /dev/vdc

ls -l /dev/disk/by-partlabel/ydb_disk_*
EOF
```

```bash
# Running disk configuration script
for  x in `seq 1 8`; do h=ydb"$x"
  scp ydb-disks.sh $h:YdbWork/
  ssh $h sudo bash YdbWork/ydb-disks.sh
done
```

```bash
# Disk formatting
for  x in `seq 1 8`; do h=ydb"$x"
  for d in 01 02; do
    ssh $h sudo LD_LIBRARY_PATH=/opt/ydb/lib /opt/ydb/bin/ydbd admin bs disk obliterate /dev/disk/by-partlabel/ydb_disk_"$d"
    echo "Status for $h $d: $?"
  done
done
```

## 4. TLS certificate generation and distribution

```bash
# Make the list of nodes
for x in `seq 1 8`; do echo ydb"$x".local; done >ydb-ca-nodes.txt
# Create the new CA and generate per-node certificates and keys
./ydb-ca-update.sh
```

```bash
# Switch to the new certificates directory
cd CA/certs/`(cd CA/certs && ls -tr) | tail -n 1`
# Distribute the keys and certificates
for h in `ls *.key | while read fn; do basename $fn .key; done | xargs echo`; do
  ssh $h rm -rf YdbWork/CA
  ssh $h mkdir YdbWork/CA
  scp "$h".key "$h":YdbWork/CA/node.key
  scp "$h".crt "$h":YdbWork/CA/node.crt
  scp ca.crt "$h":YdbWork/CA/ca.crt
  ssh $h sudo mkdir -p /opt/ydb/certs
  ssh $h sudo cp -v YdbWork/CA/\* /opt/ydb/certs/
  ssh $h sudo chown -R ydb:ydb /opt/ydb/certs
  ssh $h sudo chmod 0750 /opt/ydb/certs
done
# Switch back to the working directory
cd ../../..
```

## 5. Distribute the configuration files

Services files:

```bash
for  x in `seq 1 8`; do h=ydb"$x"
  scp ydbd-storage.service $h:YdbWork/
  scp ydbd-testdb.service $h:YdbWork/
  ssh $h sudo cp YdbWork/ydbd-storage.service /etc/systemd/system/ydbd-storage.service
  ssh $h sudo cp YdbWork/ydbd-testdb.service /etc/systemd/system/ydbd-testdb.service
done
```

The configuration file:

```bash
for  x in `seq 1 8`; do h=ydb"$x"
  scp config-8nodes.yaml $h:YdbWork/
  ssh $h sudo cp YdbWork/config-8nodes.yaml /opt/ydb/cfg/config.yaml
done
```

## 6. Start the static nodes

```bash
for  x in `seq 1 8`; do h=ydb"$x"
  ssh $h sudo systemctl daemon-reload
done
```

```bash
for  x in `seq 1 8`; do h=ydb"$x"
  ssh $h sudo systemctl start ydbd-storage
done
```

```bash
for  x in `seq 1 8`; do h=ydb"$x"
  ssh $h sudo systemctl status ydbd-storage
done
```

## 7. Initialize the cluster

Obtain the service token for administrative commands:

```bash
ydb -e grpc://ydb1.local:2135 -d /Root \
    --user root --no-password auth get-token --force >token-file
```

```bash
scp token-file ydb1.local:YdbWork/
```

Initialize the storage subsystem:

```bash
ssh ydb1
cd YdbWork
export LD_LIBRARY_PATH=/opt/ydb/lib
/opt/ydb/bin/ydbd -f token-file admin blobstorage config init --yaml-file  /opt/ydb/cfg/config.yaml
echo $?
```

Create the database:
```bash
/opt/ydb/bin/ydbd -f token-file admin database /Root/testdb create ssd:1
```

## 8. Start the dynamic nodes

```bash
# Starting the dynamic nodes
for  x in `seq 1 8`; do h=ydb"$x"
  ssh $h sudo systemctl start ydbd-testdb
done
```

```bash
for  x in `seq 1 8`; do h=ydb"$x"
  ssh $h sudo systemctl status ydbd-testdb
done
```

## 9. Create additional users, change root password

```bash
ydb -e grpc://ydb1:2135 -d /Root/testdb --user root --no-password yql -s 'CREATE USER stroppy PASSWORD "passw0rd"'
ydb -e grpc://ydb1:2135 -d /Root/testdb --user root --no-password yql -s 'ALTER GROUP ADMINS ADD USER stroppy'
ydb -e grpc://ydb1:2135 -d /Root/testdb --user root --no-password yql -s 'ALTER USER root PASSWORD "passw0rd"'
```
