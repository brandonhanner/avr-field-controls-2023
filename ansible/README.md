# Ansible Deployment

This folder contains the Ansible playbooks and templates used to deploy the
field-control software to the Raspberry Pi nodes (controller + building nodes).
Deployments are based on Docker images shipped as tarballs and on per-node
configuration rendered from Jinja templates.

## What gets deployed

- **Controller node** (`CONTROLLER` in inventories)
  - `field-controller` container
  - `mosquitto` broker container
  - `nodered` container
- **Building nodes** (numbered `"1"`-`"9"`)
  - `arduino-adapter` container

## Inventory files

Inventories live in `ansible/inventories/` and define:
- Host IPs and credentials
- The `data_root` on each host (default `/home/{{ ansible_user }}`)
- Which container tarballs to push
- Per-node config values (MQTT broker IP, serial port, relay channels, etc.)

Examples:
- `ansible/inventories/court_1.yaml`
- `ansible/inventories/court_2.yaml`
- `ansible/inventories/court_3.yaml`

## Playbooks

- `ansible/plays/provision.yaml`
  - Optional provisioning: hostname, time sync, disable wait-online.
- `ansible/plays/deploy.yaml`
  - Full deploy: push images + configs, generate compose files.
- `ansible/plays/start_all.yaml`
  - Start services on all nodes.
- `ansible/plays/stop_all.yaml`
  - Stop services on all nodes.
- `ansible/plays/reboot.yaml`
  - Reboot reachable hosts.

## How deployment works

1. **Reachability check** groups nodes into `reachable` vs `unreachable`.
2. **Project root** is resolved so templates can reference repo files.
3. **Image shipping**:
   - Each host’s `containers` list references a tarball in `exports/`.
   - `ansible/actions/docker_utilities/push_docker_image.yaml` copies the tarball,
     loads it via `docker load`, and optionally prunes old layers.
4. **Config shipping**:
   - Controller:
     - Generates `configs/config.json`
     - Copies `controller_modules/mqtt` and `controller_modules/nodered`
     - Renders `docker-compose.yaml` from
       `ansible/actions/controller/docker-compose.j2`
   - Arduino adapter:
     - Generates `configs/config.json`
     - Renders `docker-compose.yaml` from
       `ansible/actions/arduino_adapter/docker-compose.j2`

## Common commands

Run from the repo root:

```sh
ansible-playbook ansible/plays/deploy.yaml -i ansible/inventories/court_1.yaml
```

Start all services:

```sh
ansible-playbook ansible/plays/start_all.yaml -i ansible/inventories/court_1.yaml
```

Stop all services:

```sh
ansible-playbook ansible/plays/stop_all.yaml -i ansible/inventories/court_1.yaml
```

Limit to specific hosts:

```sh
ansible-playbook ansible/plays/deploy.yaml -i ansible/inventories/court_1.yaml --limit="CONTROLLER,1,2"
```

## Deployment container (optional)

`ansible/Dockerfile` + `ansible/docker-compose.yaml` provide a containerized
Ansible environment. Edit the command in `ansible/docker-compose.yaml` to point
at the inventory and playbook you want to run.

## Notes for new developers

- Image tarballs are expected in `exports/` (see inventory `containers` entries).
- The controller config uses values from inventory vars (phase durations and
  other runtime toggles are rendered into the config template).
- All Ansible tasks assume password-based SSH (see `ansible_ssh_pass` entries).
