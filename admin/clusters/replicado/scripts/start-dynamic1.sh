#! /bin/sh

nohup ./sw/ydbd server --grpcs-port 2136 --ic-port 19002 --ca certs/ca.crt --mon-port 8766 \
  --yaml-config conf/config.yaml --tenant /Root/source \
  --grpc-ca certs/ca.crt --grpc-cert certs/node.crt --grpc-key certs/node.key --mon-cert certs/web.pem \
  --node-broker grpcs://localhost:2135 >logs/source.log 2>&1 &
