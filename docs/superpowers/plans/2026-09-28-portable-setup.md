# Residential Egress Implementation Plan

**Goal:** 将已验证拓扑封装为不含生产秘密的独立 Git 仓库。

**Architecture:** 本机生成最小权限角色包，各角色本机安装；静态校验和真实网络验收分开。

**Tech Stack:** Python 标准库、OpenSSL、WireGuard、sing-box、mihomo、systemd、launchd。

**Spec:** ../../DESIGN.md

## Global Constraints

- 不修改现有代理，不提交真实配置，不承诺账号不会被封。
- 使用固定软件版本、独立服务和失败回滚；只支持设计中列出的系统。
- 住宅路由限 VPS /32，业务出站不含 DIRECT 回退。

## Review Focus

- 参数注入、非法地址与端口：生成前拒绝。
- 已有安装/符号链接/不同部署：拒绝覆盖。
- 根目录及部署目录权限：新秘密产生时即受保护。
- 中途失败：只撤销本次资源，保留可重试原始安装包。
- 假阳性：出口 IP、实际链路与配置校验不能互相替代。

## Tasks

- [x] 生成器：先写 CLI 失败测试；实现输入校验、X25519/证书生成、三角色配置、重跑保护。
- [x] 安装器：实现 plan/install/status/uninstall、校验和下载、systemd/launchd、冲突检查和回滚；测试下载校验与文件所有权边界。
- [x] 验收器：实际 HTTP 出口与 Clash API 连接证据、明确 UNKNOWN；隔离 mihomo/sing-box 正负协议测试。
- [x] 文档与交付：README 逐步命令、故障恢复、AI Skill、CI、秘密扫描、初始化仓库并从干净 clone 复测。
