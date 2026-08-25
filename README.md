# LAN Music Bridge

[简体中文（默认）](#简体中文) | [English](#english)

## 简体中文

LAN Music Bridge 是一个厂商中立、仅依赖 Python 标准库的局域网音乐桥接服务。
它可以发现 UPnP/OpenHome 播放设备、控制播放、代理经过白名单允许的网络音频，
并通过支持 HTTP Range 的服务发布按内容寻址的本地缓存文件。

本项目目前处于 Alpha 预发布阶段。协议和安全功能已经过自动测试，但尚未在所有
播放设备和网络环境中完成兼容性认证。

### 主要功能

- SSDP 设备发现，并校验响应来源与设备描述地址；
- 优先使用 OpenHome Playlist 控制，必要时回退到 UPnP AVTransport；
- 切换 OpenHome 播放源成功后再替换队列，同一设备的控制操作串行执行；
- 使用短期内存令牌代理经过白名单允许的网络音频；
- 基于 SQLite 和 SHA-256 的本地媒体缓存，支持原子写入、固定条目、按配额进行
  LRU 清理以及 HTTP Range 传输；
- 最小化并默认脱敏的 `/health` 接口，不返回标题、设备地址、源地址、令牌、
  Cookie 或队列内容；
- 仅监听回环地址的管理 API 和命令行工具；
- 面向设备本地存储集成的稳定 publisher 适配器边界；
- systemd 与 OpenWrt 打包示例、自动测试、GitHub Actions CI 和发布审计。

私有音乐平台解析器、账号登录流程、设备专有存储协议、固件、媒体文件、凭据及
家庭部署配置均不属于本仓库。

### 快速开始

运行环境需要 Python 3.11 或更高版本，并且播放设备与本服务位于可互通的组播网络。

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
install -d -m 0750 ./var/cache
cp config/config.example.toml ./config.toml
```

启动前请修改 `config.toml`。至少需要将 `public_base_url` 设置为播放设备能够访问的
桥接服务地址，并替换示例中的音频来源白名单。

```sh
lan-music-bridge --config ./config.toml validate-config
lan-music-bridge --config ./config.toml serve
```

在另一个终端中发现设备并播放媒体：

```sh
lan-music-bridge --config ./config.toml discover
lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode local --file ./track.flac
printf '%s\n' 'https://media.example/path/to/audio' | \
  lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode stream --url-stdin
```

通过标准输入传递带签名的媒体地址，可以避免它进入 Shell 历史。服务只在内存中
短暂保存流媒体地址，日志仅记录不可逆的短指纹。

运行测试和发布审计：

```sh
make check
make release-audit
```

### 使用边界

内置本地 publisher 会由桥接服务提供已经完整下载且不可变的缓存文件。将文件复制
到播放设备自身的硬盘或媒体库属于设备适配器职责，因为各设备的存储和索引协议并不
通用。详见 [适配器说明](docs/ADAPTERS.md)。

媒体端口仅适合可信局域网；管理端口强制限制在回环地址。跨 VLAN、VPN、访客网络
或互联网开放任何端口前，请先阅读[安全说明](SECURITY.md)。

本项目为独立开源软件，不代表任何设备厂商、平台或服务提供商的官方授权、认证、
合作关系或兼容性保证。

### 文档

- [架构](ARCHITECTURE.md)
- [安全说明](SECURITY.md)
- [适配器](docs/ADAPTERS.md)
- [Linux 安装、升级与回滚](docs/INSTALL-LINUX.md)
- [OpenWrt 打包](docs/INSTALL-OPENWRT.md)
- [私有部署边界](docs/MIGRATION.md)
- [发布检查清单](docs/RELEASE.md)
- [源码来源](PROVENANCE.md)
- [更新记录](CHANGELOG.md)

本项目使用 Apache License 2.0 许可证。

---

## English

LAN Music Bridge is a vendor-neutral, dependency-free Python service for discovering
UPnP/OpenHome renderers, controlling playback, proxying allow-listed network audio,
and publishing content-addressed local cache files over HTTP with byte-range support.

The project is an alpha pre-release. It has automated protocol and security tests,
but it has not been certified against every renderer or network layout.

### What is included

- SSDP discovery with responder/location origin checks;
- OpenHome Playlist control with UPnP AVTransport fallback;
- serialized per-renderer control and queue replacement only after a successful
  OpenHome Product source switch;
- network streaming through short-lived in-memory tokens;
- SQLite-indexed, SHA-256-addressed local media cache with atomic writes, pinning,
  quota-aware LRU eviction, and Range delivery;
- a minimal `/health` endpoint that never returns titles, device addresses, source
  URLs, tokens, cookies, or queue metadata;
- a loopback-only administration API and CLI;
- a stable publisher adapter boundary for device-local storage integrations;
- systemd and OpenWrt packaging examples, tests, GitHub Actions CI, and release audits.

Private provider resolvers, account login flows, device-specific storage protocols,
firmware files, media, credentials, and household deployment configuration are not
part of this repository.

### Quick start

Requirements: Python 3.11 or newer and a renderer reachable on the same multicast
domain.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
install -d -m 0750 ./var/cache
cp config/config.example.toml ./config.toml
```

Edit `config.toml` before starting. In particular, set `public_base_url` to the
bridge address that the renderer can reach and replace the example source allow-list.

```sh
lan-music-bridge --config ./config.toml validate-config
lan-music-bridge --config ./config.toml serve
```

In another terminal:

```sh
lan-music-bridge --config ./config.toml discover
lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode local --file ./track.flac
printf '%s\n' 'https://media.example/path/to/audio' | \
  lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode stream --url-stdin
```

Passing a signed media URL through stdin keeps it out of shell history. The daemon
keeps stream URLs only in memory and logs only short irreversible fingerprints.

Run the test and release gates with:

```sh
make check
make release-audit
```

### Boundaries

The built-in local publisher serves a fully downloaded immutable file from the
bridge. Copying that file into a renderer's own disk/library is deliberately an
adapter concern because storage and indexing protocols are device-specific. See
[docs/ADAPTERS.md](docs/ADAPTERS.md).

The media listener is intended for trusted LANs. The administration listener is
hard-limited to loopback. Read [SECURITY.md](SECURITY.md) before exposing any port
across VLAN, VPN, guest, or internet boundaries.

This independent project does not claim endorsement, certification, partnership,
or compatibility guarantees from any device, platform, or service provider.

### Documentation

- [Architecture](ARCHITECTURE.md)
- [Security](SECURITY.md)
- [Adapters](docs/ADAPTERS.md)
- [Linux installation and rollback](docs/INSTALL-LINUX.md)
- [OpenWrt packaging](docs/INSTALL-OPENWRT.md)
- [Private deployment boundary](docs/MIGRATION.md)
- [Release checklist](docs/RELEASE.md)
- [Source provenance](PROVENANCE.md)
- [Changelog](CHANGELOG.md)

Licensed under Apache License 2.0.
