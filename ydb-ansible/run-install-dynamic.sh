#! /bin/sh

ansible-playbook -b -i hosts-dynamic -f 20 install-dynamic.yaml
