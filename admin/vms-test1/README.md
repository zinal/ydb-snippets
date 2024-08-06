# Cluster creation and installation

VM creation:
1. Create the VM with public IP for remote access.
1. Generate the SSH key on the VM, to use for access to other VMs: `ssh-keygen -t ecdsa`
1. Edit `options.sh`, adjusting to the environment.
1. Run `01-vms.sh`

YDB installation:
1. Download playbook: https://github.com/ydb-platform/ydb-ansible/archive/refs/tags/v0.10.tar.gz
1. Unpack the playbook
1. Download YDB: https://binaries.ясубд.рф/release/24.2.6.1/yasubd-24.2.6.1-linux-amd64.tar.xz
1. Put the `ydb-ca-nodes.txt` to the `tls` subdirectory of the playbook
1. Run `ydb-ca-update.sh` in the `tls` subdirectory of playbook, to generate the certs
1. Link the certs directory as top-level TLS dir: `ln -s playbooks/tls/CA/certs/2024-08-06_13-05-45 TLS`
1. Copy the `hosts` file to the playbook directory
1. Create the `files/secrets` file, based on the example
1. Copy the `group_vars_all` file to `group_vars/all` in the playbook directory
1. Copy the `config.yaml` file to `files/config.yaml` in the playbook directory
1. `./run-install-static.sh`
1. `./run-create-database.sh`
1. `./run-install-dynamic.sh`
