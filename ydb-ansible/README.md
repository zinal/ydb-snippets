# Deploying YDB cluster with Ansible

Ansible playbooks supporting the deployment of [YDB](https://ydb.tech) clusters into VM or baremetal servers.

Currently the playbooks provided support the following scenarious:
* the initial deployment of YDB static (storage) nodes;
* the initial deployment of YDB dynamic (database) nodes;
* adding extra YDB dynamic nodes to the YDB cluster.

The following scenarious are yet to be implemented:
* configuring extra storage devices within the existing YDB static nodes;
* adding extra YDB static nodes to the existing cluster;
* removing YDB dynamic nodes from the existing cluster.

One important limitation of the current playbooks is that the cluster configuration file has to be manually created.
