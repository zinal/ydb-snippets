# Settings for mini-maint

set +u

if [ -z "$YDB_USER" ]; then
export YDB_SSL_ROOT_CERTIFICATES_FILE=/home/demo/ca.crt
export YDB_USER=root
export YDB_PASSWORD='P@$$w0rd+'
fi

export YDB_HOME=/home/demo/yasubd-23.2.12.3-linux-amd64
export YDB_STORAGE_PORT=2135
export YDB_DOMAIN='Domain0'
export YDB_CONFIG=ydbd-static.yaml

export REMOTE_USER=yc-user
export REMOTE_YDB=/opt/ydb

export LD_LIBRARY_PATH=$YDB_HOME/lib
export PATH=$PATH:$YDB_HOME/bin

set -u
