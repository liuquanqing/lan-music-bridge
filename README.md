# LAN Music Bridge

[简体中文（默认）](#简体中文) | [English](#english)

## 简体中文

LAN Music Bridge 是部署在软路由上的数播音乐中枢。它接过你有权使用的歌曲文件或
播放地址，由常开网关完成下载校验、缓存和播放控制，让播放不再依赖手机会话或临时
链接；设备支持本地曲库导入时优先走本地播放，否则使用 UPnP/OpenHome 推流。

发烧友常遇到手机投播中断、平台给出的文件版本不符合预期、数播网络播放不稳，或
同一台设备的本地播放链路表现更好。LAN Music Bridge
负责“音源已经拿到”之后的稳定交付；音源版本选择和平台登录仍由外部合法流程负责。

| 功能 | 解决的问题 |
|---|---|
| 音源接入与下载校验 | 接收本地文件或白名单播放地址；声明长度不符时拒绝入库，不做隐式转码，避免残缺文件进入播放链路。 |
| 常开缓存与容量管理 | 歌曲缓存后不再依赖手机保持连接或原始临时地址；重复播放不用再次下载，SQLite/LRU 控制软路由占用。 |
| 数播本地曲库适配（推荐） | 可通过设备适配器复制并索引到数播本地库，使用设备自己的本地播放链路；公共项目提供接口，不含通用设备适配器。 |
| UPnP/OpenHome 即时播放 | 无需等待入库即可播放，适合临时点播和不支持本地导入的设备；实际格式与音质表现取决于数播的网络播放实现。 |
| 播放控制 | 发现设备、正确切源、同设备串行控制、最后一次选歌优先，减少切歌串曲和旧请求覆盖。 |
| 安全与运维 | 六小时内存令牌隐藏上游地址，日志和健康状态默认脱敏；缓存自动清理，管理面仅限回环，并提供 OpenWrt/systemd 支持。 |

- 缓存不会自动提升音质；同一文件走相同解码路径时不会因缓存改变声音，本地播放是否
  更好取决于数播实现。
- 项目不包含音乐平台账号、登录、音源解析或音质版本选择能力。

### 快速开始

需要 Python 3.11 或更高版本。软路由和数播应位于组播可达的网络。

~~~sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
install -d -m 0750 ./var/cache
cp config/config.example.toml ./config.toml
~~~

编辑 `config.toml`，把 `public_base_url` 换成数播能访问的软路由地址，并设置允许的
音源网站。然后启动服务：

~~~sh
lan-music-bridge --config ./config.toml validate-config
lan-music-bridge --config ./config.toml serve
~~~

发现数播并播放本地文件或网络地址：

~~~sh
lan-music-bridge --config ./config.toml discover
lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode local --file ./track.flac \
  --content-type audio/flac
printf '%s\n' 'https://media.example/path/to/audio' | \
  lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode stream --url-stdin
~~~

~~~sh
make check
make release-audit
~~~

### 安全

媒体端口没有用户鉴权或 TLS，只应开放给可信局域网；`/health` 和 `/ready` 也在该
端口无鉴权提供。管理端口只允许回环地址。跨 VLAN、VPN、访客网络或互联网开放前，
请阅读[安全说明](SECURITY.md)。

公共仓库不保存平台账号、设备凭据、真实音源链接、媒体文件或部署配置。设备适配器
属于受信任代码，需要单独审查来源、许可证、权限和日志。本项目不代表任何厂商或
平台的授权、认证或兼容性保证。

### 文档

- [架构](ARCHITECTURE.md)、[安全说明](SECURITY.md)、[适配器](docs/ADAPTERS.md)
- [Linux 安装与回滚](docs/INSTALL-LINUX.md)、[OpenWrt 打包](docs/INSTALL-OPENWRT.md)
- [私有扩展边界](docs/MIGRATION.md)、[发布清单](docs/RELEASE.md)
- [源码来源](PROVENANCE.md)、[更新记录](CHANGELOG.md)

本项目使用 Apache License 2.0 许可证。

---

## English

LAN Music Bridge is a network-player hub that runs on a router. It takes a track file
or playback URL you are authorized to use, then lets the always-on gateway validate,
cache, and control delivery instead of relying on a phone session or temporary URL.
It prefers the player's local library when an import adapter is available, with
UPnP/OpenHome streaming as the fallback.

For audio enthusiasts, the recurring problems are interrupted phone casting, an
unexpected source-file version, unstable network playback, or a player whose local
path works better than its streaming path. LAN Music Bridge handles reliable delivery
after the source has been obtained; source-version selection and platform login remain
the job of an external, authorized workflow.

| Capability | Problem it solves |
|---|---|
| Source input and download validation | Accepts local files or allow-listed playback URLs. A declared-length mismatch is rejected, and no implicit transcoding is performed, keeping incomplete files out of the playback path. |
| Always-on cache and capacity management | Once cached, a track no longer depends on the phone staying connected or the original temporary URL. Replays need no new download, while SQLite/LRU limits router storage use. |
| Local-library integration (preferred) | A device adapter can copy and index tracks into the player's library, using its own local playback path. The public project defines the interface but includes no universal device adapter. |
| Immediate UPnP/OpenHome playback | Starts without waiting for a library import. It suits one-off playback and devices without local import; format support and audio performance depend on the player's network path. |
| Playback control | Discovers devices, switches sources correctly, serializes control per device, and lets the latest track choice win, reducing mixed queues and stale requests. |
| Security and operations | Six-hour in-memory tokens hide upstream URLs; logs and health state are redacted by default. Cache cleanup, loopback-only administration, and OpenWrt/systemd support keep the service manageable. |

- Caching does not improve sound automatically. Identical bytes on the same decode path
  are unchanged; whether local playback performs better depends on the player.
- The project includes no music-platform accounts, login, source resolution, or
  quality-version selection.

### Quick start

Python 3.11 or newer is required. The router and player must be multicast-reachable.

~~~sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
install -d -m 0750 ./var/cache
cp config/config.example.toml ./config.toml
~~~

Edit `config.toml`, set `public_base_url` to a router address the player can reach,
and configure the allowed source sites. Then start the service:

~~~sh
lan-music-bridge --config ./config.toml validate-config
lan-music-bridge --config ./config.toml serve
~~~

Find a player and play a local file or network URL:

~~~sh
lan-music-bridge --config ./config.toml discover
lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode local --file ./track.flac \
  --content-type audio/flac
printf '%s\n' 'https://media.example/path/to/audio' | \
  lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode stream --url-stdin
~~~

~~~sh
make check
make release-audit
~~~

### Security

The media listener has no user authentication or TLS and should be exposed only to a
trusted LAN. `/health` and `/ready` are also unauthenticated there. Administration is
loopback-only. Read [SECURITY.md](SECURITY.md) before exposing ports across a VLAN,
VPN, guest network, or the internet.

The public repository stores no platform accounts, device credentials, raw source
URLs, media, or deployment configuration. Device adapters are trusted code and need
their own provenance, license, permission, and log review. The project makes no vendor
or platform authorization, certification, or compatibility claim.

### Documentation

- [Architecture](ARCHITECTURE.md), [security](SECURITY.md), [adapters](docs/ADAPTERS.md)
- [Linux installation and rollback](docs/INSTALL-LINUX.md), [OpenWrt packaging](docs/INSTALL-OPENWRT.md)
- [Private extension boundary](docs/MIGRATION.md), [release checklist](docs/RELEASE.md)
- [Source provenance](PROVENANCE.md), [changelog](CHANGELOG.md)

Licensed under Apache License 2.0.
