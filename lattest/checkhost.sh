#! /bin/bash

set +e
host ${YDB_HOST}
ping -n -c 4 ${YDB_HOST}

exit 0
