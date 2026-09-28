# Agent entrypoint

This repository helps a traveler use their own overseas residential internet connection through an always-on home Mac and a VPS. It contains no ready-to-use proxy service or credentials.

For deployment, read `README.md`, then `skills/residential-egress-setup/SKILL.md` and `docs/OPERATIONS.md`. Use the existing scripts rather than inventing a deployment from scratch. The skill defines supported platforms, minimum inputs, traffic-path checks and recovery constraints. Installation authorization does not authorize interrupting existing production traffic for fault or reboot drills.

Never ask users to paste passwords or private keys into chat. Never publish `.private/`, generated role bundles, runtime configs or logs. Request non-secret host/role details; let users enter sudo passwords in their own terminal.

For development, run `python3 -m unittest discover -s tests -v` and `bash -n setup.sh egress/role-setup.sh egress/client-setup.sh`. Protocol smoke tests are optional and require sing-box and mihomo. Do not install generated services on the development machine just to test the installer. State the difference between offline tests, loopback protocol tests and actual three-host deployment acceptance.
