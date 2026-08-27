# LAN Music Bridge

[简体中文（默认）](#简体中文) | [English](#english)

## 简体中文

LAN Music Bridge 是部署在软路由上的数播音乐中枢，专门处理 QPlay/UPnP 推流中
最影响体验的问题：下一首接不上、播放中途无声、无法拖动进度，以及本应为 SQ 的歌曲
被当成 HQ。

它可与外置接入服务配合，由软路由统一完成音源修正、下载校验、缓存和队列提交，
再交给 OpenHome 数播按序播放。

对本地播放音质优于推流的数播，还可通过设备适配器把已校验歌曲写入本地曲库。用户仍按推流
方式选歌，实际播放改走设备自己的本地链路，从而获得更好的音质；不具备本地导入条件时，
再使用局域网推流。在部分系统中，转发推流的音质表现会略逊于本地播放；如果必须推流，
建议软路由使用稳定、低噪声的网络接口。对网络输入敏感的系统，可搭配供电和隔离更好的 HiFi USB 网卡。

| 功能 | 描述 |
|---|---|
| 推流接入与音源修正 | 外置接入服务可承接 UPnP/QPlay 推流，修正特定来源的地址或元数据，再把文件、白名单地址和有序队列交给公共核心。它不会把 MP3 伪装成 FLAC。 |
| QQ 音乐 SQ 保真（可选外置服务） | 使用手机 QQ 或 QQ 音乐扫码登录，无需在软路由输入账号密码。服务按已付费账号的实际权益请求 SQ/FLAC，并校验歌曲身份和下载文件；已确认为 SQ 的歌曲不会静默降为 HQ，HQ 也不会冒充 SQ。请求 SQ 而平台未返回合格 SQ 时会明确失败；普通/HQ 请求保留原等级。该服务尚未包含在本公共仓库内。 |
| 下载校验与本地缓存 | 支持本地文件和白名单播放地址。下载完成后核对声明长度并按 SHA-256 入库；SQLite/LRU 复用歌曲并控制磁盘占用。 |
| OpenHome 有序队列 | 一次接收完整歌曲列表，全部项目准备成功后按序替换 Playlist，并从第一首开始播放。同一数播串行执行，最后一次队列请求优先。 |
| 稳定的局域网推流 | 为歌曲生成六小时内存令牌，隐藏上游地址；支持 Range 和显式媒体类型，不做隐式转码，可供数播读取和拖动进度。 |
| 数播本地曲库适配（推荐） | 设备适配器可把已校验歌曲复制并索引到数播本地硬盘，使用设备自己的本地播放链路；对本地播放优于推流的数播，可发挥本地链路的音质优势。公共项目提供接口，具体设备需要对应适配器。 |
| 发现、控制与运维 | SSDP 自动发现数播，支持播放、暂停、停止和正确切源；提供脱敏健康状态、回环管理接口及 OpenWrt/systemd 部署支持。 |

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

发现数播并播放单曲：

~~~sh
lan-music-bridge --config ./config.toml discover
lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode local --file ./track.flac \
  --content-type audio/flac
printf '%s\n' 'https://media.example/path/to/audio' | \
  lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode stream --url-stdin
~~~

提交多曲队列时，先准备一个 JSON 文件。`mode` 可为 `local` 或 `stream`；本地相对路径
以 JSON 文件所在目录为基准，网络地址必须在配置白名单内。

~~~sh
cp config/playlist.example.json ./playlist.json
lan-music-bridge --config ./config.toml queue \
  --renderer 'uuid:your-renderer' --playlist ./playlist.json
~~~

含临时地址的列表可以通过 `--playlist -` 从标准输入传入，避免地址进入命令历史。
多曲队列只支持 OpenHome Playlist；只有 AVTransport 的设备仍可使用单曲 `play`，不会被
冒充为支持连续队列。设备执行 `DeleteAll` 后若 SOAP 写入中断，接口会明确报告设备队列
可能只更新了一部分。

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

LAN Music Bridge is a network-player hub for routers. It addresses the QPlay/UPnP
failures that most disrupt listening: a queue that will not advance, silence during a
track, broken seeking, or a track expected to be SQ appearing as HQ.

Paired with an external input service, it lets the router handle source correction,
download validation, caching, and queue submission before an OpenHome player plays the
tracks in order.

For players whose local playback sounds better than network streaming, a device adapter
can place verified tracks in the local library. The user keeps a casting-style way to
choose music, while playback runs through the player's own local path for better sound.
LAN streaming remains available when local import is not. On some systems, relayed
streaming can sound slightly worse than local playback. When streaming is required,
use a stable, low-noise network interface on the router; systems sensitive to network
input may benefit from a USB network adapter with better power and isolation.

| Capability | Description |
|---|---|
| Stream input and source correction | An external input service can accept UPnP/QPlay streams, correct source addresses or metadata, and pass files, allow-listed URLs, and an ordered queue to the public core. It does not disguise MP3 as FLAC. |
| QQ Music SQ integrity (optional external service) | Sign in by scanning a QR code in mobile QQ or QQ Music; no account password is entered on the router. The service requests SQ/FLAC within the paid account's actual entitlement and verifies track identity and the downloaded file. A track already verified as SQ is not silently downgraded to HQ, and HQ is never presented as SQ. An SQ request fails clearly if the platform returns no valid SQ; ordinary or HQ requests retain their original tier. This service is not included in the public repository. |
| Download validation and cache | Accepts local files and allow-listed URLs. Declared lengths are checked before SHA-256 storage; SQLite/LRU reuses tracks while limiting disk use. |
| Ordered OpenHome queues | Accepts a complete track list, prepares every item, replaces the Playlist in order, and starts from the first track. Operations are serialized per player and the latest queue request wins. |
| Stable LAN streaming | Six-hour in-memory tokens hide upstream addresses. Range requests and explicit media types are supported, with no implicit transcoding. |
| Player-local library integration (preferred) | A device adapter can copy and index validated tracks on the player's local disk. On players where local playback outperforms streaming, this uses the better-sounding path. The public project provides the interface; each device needs a compatible adapter. |
| Discovery, control, and operations | SSDP discovery, play/pause/stop, correct source switching, redacted health state, loopback administration, and OpenWrt/systemd deployment are included. |

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

Find a player and play one local file or network URL:

~~~sh
lan-music-bridge --config ./config.toml discover
lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode local --file ./track.flac \
  --content-type audio/flac
printf '%s\n' 'https://media.example/path/to/audio' | \
  lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode stream --url-stdin
~~~

For a multi-track queue, create a JSON array. `mode` may be `local` or `stream`;
relative local paths are resolved from the JSON file, and network URLs must match the
configured allow-list.

~~~sh
cp config/playlist.example.json ./playlist.json
lan-music-bridge --config ./config.toml queue \
  --renderer 'uuid:your-renderer' --playlist ./playlist.json
~~~

Use `--playlist -` to read lists containing temporary URLs from stdin instead of shell
history. Multi-track queues require OpenHome Playlist. AVTransport-only players remain
available through the single-track `play` command and are not presented as continuous-
queue capable. If SOAP fails after `DeleteAll`, the API reports that the device queue
may be only partially updated.

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
