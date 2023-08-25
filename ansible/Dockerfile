###############################################################
#####     Ansible Environment for Deploying Autonomy      #####
###############################################################

FROM ubuntu:22.04

RUN apt update && DEBIAN_FRONTEND=noninteractive apt install -y python3 python3-pip ansible sshpass iputils-ping rsync

RUN ansible-galaxy collection install ansible.posix
