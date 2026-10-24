#! /bin/sh

nohup ./sw/ydbd server --log-level 3 --tcp --yaml-config conf/config.yaml --grpcs-port 2135 --ic-port 19001 --mon-port 8765 --mon-cert certs/web.pem --node 1 >logs/static.log 2>&1 &

