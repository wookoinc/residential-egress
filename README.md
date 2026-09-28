# Residential Egress · 自建住宅出口

**回国时，把自己海外家里的网络带在身边。**

如果你在海外有一个家，以及一台可以常年开机的设备，就可以利用自己已有的住宅 IP 搭建个人网络出口，减少对第三方 VPN 订阅和共享节点的依赖。出口由自己掌控，也可供浏览器、命令行和 AI 工具使用。

不熟悉网络配置也可以开始：**把这个仓库的 URL 交给一个能够操作终端的 AI Agent，让它按文档检查条件、生成配置并协助安装。** 项目提供交互式向导、分角色安装脚本、可执行的验收命令和 AI Skill。

需要你提供：**家中常在线的服务器类设备、住宅宽带、一台公网 VPS，以及部署时的管理员权限。** 首版住宅设备支持 Mac mini 等 macOS 电脑，不是任意 NAS 都能直接运行。VPS、家庭网络和电力仍有成本；可靠性取决于它们持续可用。自建住宅出口不保证第三方账号不会被封。

项目由 [Wooko](https://github.com/wookoinc) 开源，采用 MIT 许可证。仓库不含任何现成账号、可用节点或个人部署凭据；密钥在你自己的电脑上生成。

## 把 URL 交给 Agent

把下面这段话发给能访问终端的 Codex、Claude Code 或其他 Agent：

```text
请帮我部署 https://github.com/wookoinc/residential-egress 。
先 clone 仓库并阅读 README.md、AGENTS.md 和
skills/residential-egress-setup/SKILL.md。
我希望回国时利用自己海外家里的住宅 IP 访问网络和使用 AI 工具。
先帮我确认家里常在线设备是否受支持，以及是否准备好了 VPS。
再收集缺少的信息，用仓库的脚本生成配置并协助安装、验收。
保留已有网络配置；密码由我在本机终端输入，不要让我把密码或密钥发到聊天里。
```

Agent 可以协助执行命令，但首次 macOS 管理员授权、云防火墙和 Clash 导入仍可能需要你操作。若要自己安装，从下面的“快速开始”继续。

## 连接方式

```text
回国后使用的电脑
  ├─ 国内 / 私网流量 → 直接连接
  └─ 其他流量 → VPS（HY2 默认 / Reality 备用）
                  → WireGuard 加密回程 → 海外家中常在线 Mac → 住宅 IP → Internet
```

两条代理线路共享同一个住宅出口；Claude / Anthropic 域名优先走住宅代理。住宅端主动连接 VPS，不需要在家中路由器做公网端口映射。建议在回国前完成安装、真实出口验证和恢复演练。

## 支持范围与准备

| 角色 | 支持 | 你需要准备 |
|---|---|---|
| 日常客户端 | macOS 12+，Apple Silicon / Intel，Clash Verge Rev | Python 3.9+、OpenSSL 1.1.1+；安装 Clash 时需要管理员授权 |
| VPS 中转 | Ubuntu 22.04 / 24.04、Debian 12，amd64 / arm64，systemd | 公网 IPv4、SSH 和 sudo；能从 GitHub 下载文件 |
| 住宅出口 | macOS 12+，Apple Silicon / Intel | Homebrew、管理员权限、常在线；与客户端为不同电脑 |

住宅端主动连 VPS，可位于 NAT/CGNAT 后面，**无需住宅路由器端口映射**。关闭住宅 Mac 上会接管默认路由的 VPN/TUN；不要在住宅 Mac 导入本项目的客户端配置。睡眠、断电、FileVault 解锁前网络不可用都会导致出口中断，脚本不修改睡眠、自动登录或磁盘加密策略。

首版只做全新安装，不自动迁移已有 sing-box / WireGuard。遇到已有路径、接口、端口或网段冲突会停止；请更换参数或使用干净机器。Windows/Linux 客户端、Linux 住宅节点尚未提供安装器。

## 快速开始

### 1. 在客户端生成安装包

克隆公开仓库：

```bash
git clone https://github.com/wookoinc/residential-egress.git
cd residential-egress
```

若收到的是 Git bundle 离线包，先执行：

```bash
git clone ./residential-egress.bundle residential-egress
cd residential-egress
```

```bash
# 首次安装依赖（已有则跳过；Homebrew 安装见 https://brew.sh）
brew install python openssl@3

# 在克隆的 residential-egress 目录内
bash setup.sh
```

向导询问 VPS 公网 IPv4、住宅公网 IPv4、未占用的私有 /30 网段。住宅公网 IP 请在**住宅 Mac** 上获取：

```bash
curl --noproxy '*' -4 --fail --max-time 20 https://api.ipify.org
```

也支持 AI/自动化使用的非交互命令。下面两个地址为文档示例，必须换成自己的：

```bash
bash setup.sh init \
  --vps 203.0.113.10 \
  --home-egress 198.51.100.20
```

生成在 `.private/deployment/`：

```text
vps/       VPS 安装包：仅 VPS 所需的配置和秘密
home/      住宅 Mac 安装包：仅住宅端所需的配置和秘密
client/    Clash 配置、API 密钥和客户端安装入口
```

这些目录有真实凭据，保存在自己的安全位置。默认已被 Git 忽略，自定义输出目录也自带 `.gitignore`。**不要上传安装包、分享 clash.yaml，或用 `git add -f`。** 不要把三端整个目录全部传给 VPS。重新运行 init 不会覆盖旧目录或轮换密钥。

高级参数见 `bash setup.sh init --help`：端口默认 UDP 8443（HY2）、TCP 443（Reality）、UDP 51820（WG）、住宅内网 8388（SS）。默认 WG 网段 `10.77.0.0/30`、接口别名 `re0`。改网段必须重新生成同一套三端包。Reality 默认握手域名 `www.microsoft.com`；如果 VPS 无法访问其 TLS 1.3 服务，用 `--reality-domain` 指定可访问的合适域名。

### 2. 在 VPS 安装

先在云控制台放行 **TCP 443、UDP 8443、UDP 51820** 入站，保留管理 SSH。若改端口，按实际参数放行。住宅 SS 8388 不对公网开放。

客户端终端中设置自己的 SSH 目标并复制 VPS 包（首次连接核对 SSH 主机指纹）：

```bash
VPS_SSH=ubuntu@203.0.113.10  # 换成自己的用户名和 VPS 地址/SSH alias
ssh "$VPS_SSH" 'umask 077; mkdir -p ~/residential-egress-vps'
scp -r .private/deployment/vps/. "$VPS_SSH:residential-egress-vps/"
ssh -t "$VPS_SSH" 'cd ~/residential-egress-vps && bash setup.sh'
```

这一步安装系统依赖、核对下载文件 SHA256，再创建独立的 `residential-egress.service` 和 `wg-quick@re0.service`。不覆盖系统已有的 `/etc/sing-box`，不更改默认路由、IP forwarding 或防火墙。

如果启用了 UFW，按实际端口执行下面命令；没有使用 UFW 就使用自己的防火墙管理方式，**不要为此开启/重置防火墙**：

```bash
sudo ufw allow 443/tcp comment residential-egress
sudo ufw allow 8443/udp comment residential-egress
sudo ufw allow 51820/udp comment residential-egress
```

### 3. 在住宅 Mac 安装

通过 AirDrop、加密移动盘或 SCP 把 `home/` **整个目录**放到住宅 Mac。无需对公网开放住宅 SSH。若它已有可用 SSH，在客户端可执行：

```bash
HOME_SSH=home-mac  # 换成你已经配置好的 SSH alias
ssh "$HOME_SSH" 'umask 077; mkdir -p ~/residential-egress-home'
scp -r .private/deployment/home/. "$HOME_SSH:residential-egress-home/"
```

在**住宅 Mac 的终端**运行（使用普通用户，脚本会在需要时请求 sudo）：

```bash
cd ~/residential-egress-home
bash setup.sh
```

安装器会安装缺少的 Homebrew 依赖，部署专用 sing-box 二进制及两个系统 LaunchDaemon，住宅 WG 只允许 VPS 的 `/32` 地址，不把住宅端默认路由指向 VPS。每次开机由 launchd 启动；实际重启可用性仍需自行验收。

### 4. 在客户端启用

```bash
bash .private/deployment/client/setup.sh
```

脚本安装/打开 Clash Verge Rev，并在 Finder 定位配置。首次仍需要以下 GUI 操作：

1. Clash Verge → 订阅/Profiles → 新建/本地 → 选择 `.private/deployment/client/clash.yaml`，启用该订阅。文件使用合法 YAML 的 JSON 语法，不需要手工改格式。
2. 安装/开启 Clash 服务模式，启用 **TUN、系统代理**，接受 macOS 管理员授权。
3. 保持 **规则模式**，PROXY 组选择 `HOME-HY2`；如果客户端网络封 UDP，可手动选择 `HOME-REALITY`。
4. 核对实际运行配置：Clash 可能覆盖端口、DNS、IPv6、API、TUN。首版预期 IPv6 关闭；如 App 开启 IPv6，请关掉并检查实际状态。

TUN 和系统代理可一起使用，它们把不同应用流量交给同一内核。两者同时启用不等于经过两次远端代理。

### 5. 验收出口（必须做）

客户端在仓库目录执行：

```bash
python3 manage.py verify
python3 manage.py verify --tun
```

每条验收要求：**实际返回预期住宅 IP，并从 Clash API 捕获这条新连接的住宅代理链**。第二条还要求观察到 Tun 入站。HTTP 请求被限速以便捕获连接；一次检查最多约 30 秒。失败或无法取得证据返回非零，不会把 UNKNOWN 当作通过。

默认代理 `127.0.0.1:7897`、API `127.0.0.1:19090`，密钥来自生成的 client/api-secret。若 Clash 覆盖了它们，用**实际运行值**：

```bash
python3 manage.py verify --proxy http://127.0.0.1:7897 \
  --api http://127.0.0.1:19090 --secret-file /path/to/runtime-api-secret

# Clash 服务模式若只开放 Unix socket，使用实际路径；不要猜 UID：
python3 manage.py verify --tun \
  --socket /actual/path/to/verge-mihomo.sock \
  --secret-file /path/to/runtime-api-secret
```

不要把 API secret 发给别人；secret-file 仅含一行密钥，权限设为 0600。这个验证器不修改 Clash 配置或节点选择。

在 Clash 连接面板确认国内网站命中 DIRECT、Claude/Anthropic 命中 PROXY；分别选择两个节点并重跑验收。服务启动、WireGuard 有握手、端口可连接和 HTTP 200 都不能代替出口验收。更多故障/UDP/重启检查见 [运维与恢复](docs/OPERATIONS.md)。

## 一键覆盖到什么程度

- 客户端 `bash setup.sh` 生成所有密钥和配置；不需要手填 UUID、密码、WG 公钥或证书指纹。
- VPS 和住宅 Mac 各运行一次 `bash setup.sh`，完成依赖、安装、开机启动。
- 云防火墙授权、跨机器传包、macOS 密码/弹窗、Clash 首次导入需要用户操作或已有管理通路。脚本不会接管你的云账号或猜管理员密码。
- 首版不提供无人值守升级、证书自动轮换、自动住宅 IP 跟踪；避免把一次安装做成持续修改网络的后台程序。

## 让 AI 来安装

给 Codex / Claude Code 这段指令即可：

```text
请阅读 https://github.com/wookoinc/residential-egress 的 README.md、AGENTS.md
和 skills/residential-egress-setup/SKILL.md，
按里面的流程帮我部署。我会提供 VPS SSH、住宅 Mac 的访问方式和住宅公网 IP。
先检查机器角色、现有代理、端口与网段，再用仓库脚本生成和安装。
保留现有配置；没有实际出口与链路证据时，不要把部署称为验收通过。
```

也可以把 skill 文件夹复制到 `~/.codex/skills/` 或 `~/.claude/skills/`，然后调用 `$residential-egress-setup` 或 `/residential-egress-setup`。Skill 会要求定位仓库，安装步骤由这里的可测试脚本实现。[AI Skill](skills/residential-egress-setup/SKILL.md)

## 开发验证

```bash
python3 -m unittest discover -s tests -v
bash -n setup.sh egress/role-setup.sh egress/client-setup.sh

# 可选：真实协议隔离测试；不会开启 TUN/改路由/安装服务
python3 tests/protocol_smoke.py \
  --sing-box /path/to/sing-box \
  --mihomo /path/to/mihomo
```

sing-box 锁定 1.14.2，四平台下载摘要在 `versions.json`；更新版本要核对官方发布摘要并重新测试。客户端隔离测试使用 mihomo 1.19.31；Clash GUI 由 Homebrew 安装当前版本，应重新验收实际运行配置。

完整的“陌生机器三端安装 + 重启 + 公网出口 + TUN”不能由本地单元测试保证。已验证范围与未验证项见 [验证记录](docs/VALIDATION.md)。

## 原理与上游依据

VPS 只有一个业务出站：绑定 `re0` 的 Shadowsocks，目标为住宅 WG 地址；无 VPS DIRECT 业务出口。Clash 的 PROXY 组只有 HY2 和 Reality。住宅端失联时，代理业务应失败。**这不是操作系统级 kill switch**：退出 Clash、禁用 TUN/系统代理、应用显式绕过代理或修改分流规则后，流量可能直连。国内、私网、VPS 管理连接原本就设计为 DIRECT。

- [sing-box HY2 / BBR 配置](https://sing-box.sagernet.org/configuration/inbound/hysteria2/)
- [sing-box VLESS / Reality](https://sing-box.sagernet.org/configuration/inbound/vless/)
- [mihomo TLS 证书指纹](https://wiki.metacubex.one/config/proxies/tls/)
- [WireGuard 安装](https://www.wireguard.com/install/)
- [Clash Verge Rev 文档](https://www.clashverge.dev/)

代码采用 MIT 许可证；第三方软件适用各自许可证。
