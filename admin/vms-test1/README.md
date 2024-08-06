# Cluster creation and installation

VM creation:
1. Create the VM with public IP for remote access.
2. Generate the SSH key on the VM, to use for access to other VMs: `ssh-keygen -t ecdsa`
3. Edit `options.sh`, adjusting to the environment.
4. Run `01-vms.sh`

YDB installation:
1. Download playbook: https://github.com/ydb-platform/ydb-ansible/archive/refs/tags/v0.10.tar.gz
2. Unpack the playbook
3. Put the `ydb-ca-nodes.txt` to the `tls` subdirectory of the playbook
4. Run `ydb-ca-update.sh` in the `tls` subdirectory of playbook, to generate the certs
5. Link the certs directory as top-level TLS dir: `ln -s playbooks/tls/CA/certs/2024-08-06_13-05-45 TLS`
6. Copy the `hosts` file to the playbook directory
7. Create the `files/secrets` file, based on the example
8. Copy the `group_vars_all` file to `group_vars/all` in the playbook directory
9. Copy the `config.yaml` file to `files/config.yaml` in the playbook directory
10. `./run-install-static.sh`
11. `./run-create-database.sh`
12. `./run-install-dynamic.sh`
