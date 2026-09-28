# 验证记录

2026-09-28，首版。

## 已完成

- macOS arm64 / Python 3.14：15 项自动测试通过，覆盖角色秘密隔离、无 DIRECT 回退、住宅 WG /32、输入拒绝、重跑不轮换密钥、下载摘要和压缩包检查、卸载所有权、macOS 路由缩写、停止失败保留恢复材料、独立服务检查、WG 地址就绪等待、出口/chain 判定。
- sing-box 1.14.2 官方 darwin-arm64 发布包 SHA256 与版本锁匹配。
- 实际 sing-box 1.14.2 + mihomo 1.19.31 隔离进程：HY2→SS HTTP 成功；Reality→SS HTTP 成功；错误 pin 拒绝；错误密码拒绝；住宅 SS 停止后 HY2 与 Reality 新客户端均失败；恢复 SS 后 HY2 再次成功。
- 生成的两端 sing-box 配置经过真实 `sing-box check`；隔离版客户端配置经过真实 `mihomo -t`。
- Shell 语法检查、Python 编译、Skill 格式校验通过。
- 独立代码审查发现的路由检测、服务状态判断、停止失败清理、WG 地址就绪竞态均已修复，并增加回归测试。
- 已扫描待提交源文件，未包含原部署的公网 IP、主机别名、本地用户路径或 PEM 私钥。
- 从独立 `git clone --no-local` 克隆重新运行 15 项测试、生成器、两端 plan、七项真实协议检查均通过；生成凭据之后 Git 工作区仍干净。

## 验证边界

协议测试全部绑定 loopback，不改现有代理、TUN、默认路由或系统服务。为实现单机隔离测试，将 WG 地址换为 loopback、去掉 SS 出站 bind_interface，并关闭测试客户端 TUN/DNS/地理分流。因此这证明了协议配置与拒绝路径，**不能证明新安装器已经在三台陌生机器上完成部署**。

尚未实测：全新 Linux systemd 安装/卸载、住宅 macOS launchd 安装/卸载、真实 WireGuard 穿越网络、真实公网出口、TUN/国内分流、真实 UDP、IPv6 泄漏检查、目标设备重启恢复。README 提供目标设备验收步骤；这些项目必须在部署后逐项确认。

CI 工作流会在 Ubuntu/macOS 和 Python 3.9/3.13 上运行离线测试；在 GitHub 首次实际运行之前，不把工作流定义当作 CI 已通过。

本机尝试 Python 3.9 Linux Docker 复测，但一次性容器持续停留在 Created 状态（没有启动测试进程），限时结束并清理了本次容器。此项结果为 UNKNOWN，没有据此宣称 Linux 实测通过，也未修改 Docker 或其他容器。
