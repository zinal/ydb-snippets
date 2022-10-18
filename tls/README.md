# TLS certificate generation script for YDB

In order to simplify generation and re-generation of certificates for YDB cluster, the `ydb-ca-update.sh` script has been created.
It reads the list of node host names from `ydb-ca-nodes.txt` file, one name per line, which needs to be located in the current directory.
Host names should be specified exactly as they are defined in the YDB cluster configuration file.

The generated certificates are written into the directory structure in the `CA` subdirectory, which is created if missing.
In case the certificate authority is not initialized yet, private CA key and certificate are generated.
For each node listed in the `ydb-ca-nodes.txt` file, each invocation of the script generates the new key and new certificate signed by the private CA.
All generated per-host files are put into `CA/certs/YYYY-MM-DD_hh-mi-ss` subdirectory.
