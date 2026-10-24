#! /bin/sh

nohup ./sw/ydbd server --grpcs-port 2137 --ic-port 19003 --ca certs/ca.crt --mon-port 8767 \
  --yaml-config conf/config.yaml --tenant /Root/target \
  --grpc-ca certs/ca.crt --grpc-cert certs/node.crt --grpc-key certs/node.key --mon-cert certs/web.pem \
  --node-broker grpcs://localhost:2135 >logs/target.log 2>&1 &
