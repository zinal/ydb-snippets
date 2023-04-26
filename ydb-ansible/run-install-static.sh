#! /bin/sh

ansible-playbook -b -i hosts-static -f 20 install-static.yaml
