#!/usr/bin/env bash

# set -v

ZONE_STATIC="0-15"
ZONES_DYNAMIC="16-31 32-47 48-63 64-79 80-95"

YDBD_PATH=${YDBD_PATH:-`pwd`/ydbd/bin/ydbd}
YDBD_LIB_PATH=${YDBD_LIB_PATH:-`pwd`/ydbd/lib}
BASE_PATH=$(dirname -- "${BASH_SOURCE[0]}")
CONFIG_PATH="${BASE_PATH}/config"
LOGS_PATH="${BASE_PATH}/logs"
export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:$YDBD_LIB_PATH"

need_init=0
disk="/dev/vdb"
cfg1="pig-static.yaml"
cfg2="pig-dynamic.yaml"
if [[ ! -f "$CONFIG_PATH/pig-prepared.txt" ]]; then
    read -p "Drive $disk is going to be fully wiped. All data it contains will be lost. Enter (yes) or (y) if you want to continue: " safeguard
    case $safeguard in
      [Yy]* ) echo "You have confirmed, proceeding.";;
      * ) echo "You have chosen not to continue, aborting."; exit 1;
    esac
    disk_by_partlabel="/dev/disk/by-partlabel/pig-drive"
    sudo parted "$disk" mklabel gpt -s
    sudo parted -a optimal "$disk" mkpart primary 0% 100% 2>/dev/null
    sudo parted "$disk" name 1 "pig-drive"
    sudo partx --u "$disk"
    sleep 1 # chown fails otherwise
    sudo chown "$(whoami)" "$disk_by_partlabel"
    $YDBD_PATH admin bs disk obliterate "$disk_by_partlabel"
    touch "$CONFIG_PATH/pig-prepared.txt"
    need_init=1
fi
echo Starting storage process...
mkdir -p "$LOGS_PATH"
taskset --cpu-list ${ZONE_STATIC} $YDBD_PATH server --yaml-config "$CONFIG_PATH/$cfg1" --node 1 --grpc-port 2136 --ic-port 19001 --mon-port 8765 \
  --log-file-name "$LOGS_PATH/storage_start.log" > "$LOGS_PATH/storage_start_output.log" 2>"$LOGS_PATH/storage_start_err.log" &
sleep 3
grep "$LOGS_PATH/storage_start_err.log" -v -f "$CONFIG_PATH/exclude_err.txt"
if [[ $? -eq 0 ]]; then
  echo Errors found when starting storage process, cancelling start script
  exit
fi
if [ $need_init -eq 1 ]; then
  echo Initializing storage...
  $YDBD_PATH -s grpc://localhost:2136 admin blobstorage config init --yaml-file "$CONFIG_PATH/$cfg1" > "$LOGS_PATH/init_storage.log" 2>&1
  if [[ $? -ge 1 ]]; then
    echo Errors found when initializing storage, cancelling start script, check logs/init_storage.log
    exit
  fi
fi
echo Registering database...
$YDBD_PATH -s grpc://localhost:2136 admin database /Root/test create ssd:5 > "$LOGS_PATH/db_reg.log" 2>&1
if [[ $? -ge 1 ]]; then
  echo Errors found when registering database, cancelling start script, check "$LOGS_PATH/db_reg.log"
  exit
fi
echo Starting database processes...
pnum=1
for ZONE_DYNAMIC in ${ZONES_DYNAMIC}; do
  $YDBD_PATH server --yaml-config "$CONFIG_PATH/$cfg2" --tenant /Root/test \
    --node-broker localhost:2136 --grpc-port $(( 31000 + ${pnum} )) --ic-port $(( 32000 + ${pnum} )) --mon-port $(( 33000 + ${pnum} )) \
    --log-file-name "$LOGS_PATH/db_start.${pnum}.log" > "$LOGS_PATH/db_start_output.${pnum}.log" 2>"$LOGS_PATH/db_start_err.${pnum}.log" &
  pnum=$(( ${pnum} + 1 ))
done
sleep 3
grep "$LOGS_PATH/db_start_err.0.log" -v -f "$CONFIG_PATH/exclude_err.txt"
if [[ $? -eq 0 ]]; then
  echo Errors found when starting database process, cancelling start script
  exit
fi
echo "
Database started. Connection options for YDB CLI:

-e grpc://localhost:2136 -d /Root/test
"
