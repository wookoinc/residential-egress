# 运维、验收与恢复

## 查看安装计划与状态

在对应机器的角色安装包目录运行：

```bash
bash setup.sh plan
bash setup.sh status
```

plan 不需要管理员权限；status 需要 sudo。WG latest-handshakes 是 Unix 时间戳，0 表示从未握手；有握手只证明两端 WG 通路，不证明住宅上网正常。不要公开 `wg showconf`、配置文件或完整 debug 日志。

VPS：

```bash
sudo systemctl status residential-egress.service wg-quick@re0.service
sudo journalctl -u residential-egress.service --since '10 minutes ago'
sudo wg show re0 latest-handshakes
```

住宅 Mac：

```bash
sudo launchctl print system/org.residential-egress.wireguard
sudo launchctl print system/org.residential-egress.proxy
sudo tail -n 50 /etc/residential-egress/service.log
```

住宅日志不自动轮转，定期查看体积；不要把包含访问目的地的日志公开上传。系统启动前 FileVault 未解锁、机器睡眠、住宅上行故障都不是 Restart 能修复的。

## 常见失败

| 现象 | 排查 |
|---|---|
| OpenSSL 报错 | 需要 X25519 和 `req -addext`，macOS 使用 Homebrew openssl@3；从 `bash setup.sh` 进入会配置 PATH |
| GitHub 下载失败 | 检查该机器到 GitHub 的连接；失败不会忽略摘要校验或换不明镜像 |
| 端口/路径/接口冲突 | 保留现有安装；新部署换端口或使用另一台机器。不要直接删生产配置 |
| 住宅网段冲突 | 重新生成一套包，指定未占用的 `--subnet`；三端必须同一套 |
| 住宅 Mac 有 TUN/VPN | 关闭住宅 Mac 的默认路由 VPN，不要把客户端配置导入住宅 Mac |
| WG 无握手 | VPS 云防火墙及主机防火墙 UDP 51820；住宅出站 UDP；两边必须同一套包 |
| HY2 不通、Reality 通 | 客户端到 VPS 的 UDP 8443 可能不可用；选择 Reality 后重新验收 |
| 服务启动后不断退出 | 读服务日志；住宅 SS 只能绑定 WG 地址，WG 必须先起来；Reality 握手域名要可用 |
| verify 返回 401/连接拒绝 | Clash 覆盖了 API 地址或密钥；读实际 runtime 设置，用 --api/--socket/--secret-file |
| IP 正确但 UNKNOWN | 未捕获同一连接 chain，不能视为通过；确认 API 属于实际接管流量的内核 |
| 住宅 IP 改变 | 在住宅 Mac 独立确认新公网 IP，排除 VPN 后，用 verify --expected-ip 新IP；不要自动信任客户端观测到的地址 |

## 故障阻断验收

应在你能直接操作住宅 Mac、VPS 有云控制台恢复通路时做。不要停止自己当前 SSH 依赖的代理通路。用户当前工作会受影响，先约定短暂中断窗口。

1. 两个节点分别运行 verify，记录均为住宅出口。
2. 在住宅 Mac 的本地终端停止本项目的 SS 服务：

   ```bash
   sudo launchctl bootout system/org.residential-egress.proxy
   ```

3. 关闭 Clash 现有连接，并为每个节点重新发起请求。预期两条代理路径均失败且没有拿到 VPS/客户端公网 IP。检查 VPS 日志确认 `home-only` 后端连接失败；单纯“超时”无法独立证明故障阻断。
4. 在住宅 Mac 恢复：

   ```bash
   sudo launchctl bootstrap system /Library/LaunchDaemons/org.residential-egress.proxy.plist
   ```

5. 重跑两个节点出口验收。恢复没通过就继续修复，不把测试标为完成。

仓库的 `tests/protocol_smoke.py` 以全新 mihomo 进程验证错误证书、错误密码、后端停止和恢复；它不停止真实住宅服务，也不替代上述实际三机验收。

## UDP、分流、IPv6 与重启

- 真 UDP 测试：用 NTP/123 或另一个已知 UDP 服务，检查响应协议内容及请求匹配字段，并在 Clash API 核对该连接经过住宅节点。端口能打开、抓到任意 UDP、HTTP/3 标志都不够。首版自动 verify 只验证 TCP HTTP，不声称验收 UDP。
- 国内网站在连接面板应为 DIRECT，Claude/Anthropic 应走 HOME-HY2 或 HOME-REALITY。检查是当前实际 runtime 配置。
- 生成配置关闭 IPv6，但 Clash GUI 可能覆盖。检查实际 DNS/IPv6 设置和主机全局 IPv6 地址；未检查或命令失败时记为 UNKNOWN，不报告无泄漏。
- 分别测试住宅 Mac、VPS 重启后自行恢复，再测客户端睡眠唤醒、网络切换。由操作者安排；脚本从不擅自重启机器。

## 证书、备份与升级

生成的自签证书有效期 365 天，Clash 固定 SHA256 叶子证书指纹。定期查看：

```bash
openssl x509 -in .private/deployment/vps/server.crt -noout -dates
```

不要单独替换证书、关闭校验或手工轮换某一端密钥。首版通过**新的输出目录生成整套包，安排维护窗口，先卸载旧三端服务，再安装新的一套并导入新客户端配置**进行重新部署。旧安装包保存到新部署验收通过之后。这个过程有停机时间，不是无缝升级。

回退时卸载新部署，用旧 bundle 安装并重新激活旧 Clash 订阅。不能在住宅出口不通时依赖它自己进行恢复；优先本地终端和 VPS 控制台。

## 卸载

先让客户端切回部署前的订阅/网络，再在**对应原始角色安装包目录**：

```bash
bash setup.sh uninstall
```

只卸载部署 ID 匹配且服务文件未被外部修改的资源。停止服务/接口失败会保留配置及恢复材料并报错，不声称卸载完成。安装失败通常撤销本次文件；如果无法停止新服务，也保留文件用于修复。

不会卸载系统依赖、删除 Homebrew、移除系统组、重置防火墙或修改其他服务。若曾手工加 UFW/云端规则，确认没有其他用途后手工撤销对应端口。客户端在 GUI 切回旧订阅，并按需要删除本项目订阅；脚本不代替你选择原有网络方案。

保留的路径：VPS/住宅配置与专用二进制在 `/etc/residential-egress`；VPS WG 配置 `/etc/wireguard/re0.conf`；系统服务仅使用 `residential-egress` / `org.residential-egress.*` 名称。
