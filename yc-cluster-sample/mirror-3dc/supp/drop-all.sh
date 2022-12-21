#! /bin/sh
# Удаление виртуальных машин Yandex Cloud.

checkLimit() {
  grep "The limit on maximum number of active operations has exceeded" mkinst.tmp | wc -l | (read x && echo $x)
}

echo "Dropping VMs..."
for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
  vm_name="${host_base}-s${i}"

  echo "...${vm_name}"
  while true; do
    yc compute instance delete --name ${vm_name} --async >mkinst.tmp 2>&1
    cnt=`checkLimit`
    if [ "$cnt" == "0" ]; then break; else sleep 10; fi
  done
done
cnt=`grep "ERROR:" mkinst.tmp | wc -l`
if [ $cnt -gt 0 ]; then
    echo "*** ERROR: VM removal failed!"
    cat mkinst.tmp
    exit 1
fi

# End Of File
