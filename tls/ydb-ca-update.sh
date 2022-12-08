#! /bin/sh

set -e
set +u

NODES_FILE=ydb-ca-nodes.txt
KEY_BITS=4096

[ -d CA ] || mkdir CA
cd CA

[ -d secure ] || mkdir secure
[ -d certs ] || mkdir certs
[ -d nodes ] || mkdir nodes

if [ ! -f ca.cnf ]; then
    echo "** Generating CA configuration file"
cat >ca.cnf <<EOF
[ ca ]
default_ca = CA_default

[ CA_default ]
default_days = 365
database = index.txt
serial = serial.txt
default_md = sha256
copy_extensions = copy
unique_subject = no

[ req ]
prompt=no
distinguished_name = distinguished_name
x509_extensions = extensions

[ distinguished_name ]
organizationName = YDB
commonName = YDB CA

[ extensions ]
keyUsage = critical,digitalSignature,nonRepudiation,keyEncipherment,keyCertSign
basicConstraints = critical,CA:true,pathlen:1

[ signing_policy ]
organizationName = supplied
commonName = optional

[ signing_node_req ]
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth,clientAuth

# Used to sign client certificates.
[ signing_client_req ]
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = clientAuth
EOF
fi

if [ ! -f secure/ca.key ]; then
    echo "** Generating CA key"
    openssl genrsa -out secure/ca.key ${KEY_BITS}
fi

if [ ! -f certs/ca.crt ]; then
    echo "** Generating CA certificate"
    openssl req -new -x509 -config ca.cnf -key secure/ca.key -out certs/ca.crt -days 1830 -batch
fi

[ -f index.txt ] || touch index.txt
[ -f serial.txt ] || (echo 01 >serial.txt)

# The '..' part here is due to changed current directory
if [ ! -f ../${NODES_FILE} ]; then
    echo "** Missing file ${NODES_FILE} - EXIT"
    exit 0
fi

make_node_conf() {
    if [ ! -f nodes/"$1".cnf ]; then
        echo "** Creating node configuration file for $1..."
cat > nodes/"$1".cnf <<EOF
# OpenSSL node configuration file
[ req ]
prompt=no
distinguished_name = distinguished_name
req_extensions = extensions

[ distinguished_name ]
organizationName = YDB

[ extensions ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1=$1
EOF
      if [ ! -z "$2" ]; then
        vn=1
        for nn in $2; do
          vn=`echo "$vn + 1" | bc`
          echo "DNS.$vn=$nn" >>nodes/"$1".cnf
        done
      fi
    fi
}

make_node_key() {
    if [ ! -f nodes/"$1".key ]; then
         echo "** Generating key for node $1..."
         openssl genrsa -out nodes/"$1".key ${KEY_BITS}
    fi
}

make_node_csr() {
    if [ ! -f nodes/"$1".csr ]; then
        echo "** Generating CSR for node $1..."
        openssl req -new -sha256 -config nodes/"$1".cnf -key nodes/"$1".key -out nodes/"$1".csr -batch
    fi
}

make_node_cert() {
    if [ ! -f nodes/"$1".crt ]; then
        echo "** Generating certificate for node $1..."
        openssl ca -config ca.cnf -keyfile secure/ca.key -cert certs/ca.crt -policy signing_policy \
            -extensions signing_node_req -out nodes/"$1".crt -outdir nodes/ -in nodes/"$1".csr -batch
    fi
}

DEST_NAME=`date "+%Y-%m-%d_%H-%M-%S"`
[ -d certs/"$DEST_NAME" ] || mkdir certs/"$DEST_NAME"
cp -v certs/ca.crt certs/"$DEST_NAME"/

move_node_files() {
    mv -v nodes/"$1".crt certs/"$DEST_NAME"/
    mv -v nodes/"$1".key certs/"$DEST_NAME"/
    mv -v nodes/"$1".csr certs/"$DEST_NAME"/
    mv -v nodes/*.pem certs/"$DEST_NAME"/
}

# The '..' part here is due to changed current directory
cat ../${NODES_FILE} | while read node node2; do
    if [ ! -z "$node" ]; then
        make_node_conf "$node" "$node2"
        make_node_key "$node"
        make_node_csr "$node"
        make_node_cert "$node"
        move_node_files "$node"
    fi
done

echo "All done. Certificates are in CA/certs/$DEST_NAME"
