---
name: residential-egress-setup
description: Deploy, verify or remove this repository's residential-egress topology using its role bundles. Use when the user wants HY2/Reality via a VPS and WireGuard to their own residential Mac, or asks to install this repository.
---

# Residential Egress Setup

Locate the repository containing `manage.py`, `versions.json`, and `README.md`. If this skill was copied into a global skills directory, ask for the cloned repository path rather than assuming relative paths resolve. Read its README and `docs/OPERATIONS.md` before running deployment commands.

## Scope and inputs

Support macOS client, Ubuntu 22.04/24.04 or Debian 12 VPS with systemd, and a separate always-on macOS residential host. Collect VPS public IPv4/SSH target, residential access method and independently observed public IPv4. Confirm the residential host is not using a capturing VPN/TUN. Ask only for missing inputs; use the user's existing deployment authorization.

Inspect existing services, ports and routes read-only. The scripts support fresh installs, not migration. If `/etc/residential-egress`, interface alias `re0`, its service names or selected subnet conflict, preserve them and select another host/subnet/port as appropriate. Never delete preexisting resources to make an installer pass.

## Execute

1. Run `bash setup.sh init --help`. Generate once using `bash setup.sh init --vps IP --home-egress IP` with any required port/subnet overrides. Reuse the generated bundle on retry. Do not expose passwords, key material, full configs or debug logs in chat.
2. Transfer only `vps/` to the VPS and only `home/` to the residential host over the user's authenticated channel. Use private remote directories (`umask 077`). Never upload the entire `.private` tree to a third party.
3. Run each bundle's `bash setup.sh plan`; compare the paths/ports to the inspected machine. Run `bash setup.sh` within authorized scope. Use a terminal for sudo prompts; never solicit passwords in chat. Homebrew runs as the ordinary Mac user.
4. Confirm cloud and host firewall rules for the selected VPS ports while preserving SSH. Do not enable/reset a firewall as a shortcut. Confirm the user has a management route independent of the new residential proxy.
5. On the client run `bash .private/deployment/client/setup.sh`, then guide or use available UI tools to import the local `clash.yaml`, authorize service/TUN and enable rule mode. Do not overwrite unrelated profiles. Read actual runtime settings because Clash may override source YAML.
6. Run `python3 manage.py verify` and `python3 manage.py verify --tun` against the actual control API/socket and secret. Select each residential node explicitly and test each. Check domestic DIRECT and Claude/Anthropic PROXY in current connection evidence. Do not infer the path from HTTP 200, a listening port, a config file, or an IP alone.

## Invariants and recovery

- Client PROXY contains only HOME-HY2 and HOME-REALITY, never DIRECT. VPS business outbound is only SS bound to re0. Residential WG AllowedIPs is only VPS WG /32, never a default route.
- HY2 uses BBR with pinned certificate; do not add invented bandwidth values or disable certificate verification.
- Never stop a service carrying your own management connection without a working independent recovery route. Fault and reboot drills require a user-agreed interruption window; installation alone does not imply permission to interrupt existing work.
- Follow the role bundle's uninstall for rollback. If stopping fails, preserve recovery files and repair the service state. Do not regenerate credentials as a retry strategy.
- If any inspection fails, record UNKNOWN, not PASS. Account availability and “no future bans” are not acceptance criteria the network installer can guarantee.

## Completion report

Report role installation status, selected node, observed exit IP, correlated chain/TUN evidence, domestic split outcome, and whether real UDP, failure recovery and reboot were actually tested. Name any remaining GUI/admin/network steps and their exact commands. Separate local protocol test evidence from full three-host acceptance. Never claim complete deployment based only on unit tests or enabled services.
