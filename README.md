# LAN Music Bridge

[简体中文（默认）](#简体中文) | [English](#english)

## 简体中文

### 把合法音源接成一条稳定、可审计的局域网播放链路

LAN Music Bridge 部署在软路由或常开 Linux 网关上，把合法音源、可验证缓存、
设备本地发布适配和播放器控制接成一条可审计的局域网链路。推荐优先使用设备本地
播放；需要即时播放或设备不支持本地导入时，再使用 UPnP/OpenHome 推流。

音源版本与质量、临时下载地址、桥接端协议/格式能力、控制会话和设备实际播放路径
通常由不同组件负责。任何一环处理不当，都可能造成中断、选错文件版本、静默转码，
或没有走到设备更成熟的本地解码与播放实现。账号、签名地址和凭据也不应进入日志
或公共核心。

推荐链路：

~~~text
用户自己的外部音源流程（提供文件或白名单 URL）
              |
              v
完整下载 -> SHA-256 内容寻址缓存
              |
              +-> device-local publisher adapter（推荐，设备扩展）
              |
              +-> UPnP/OpenHome 推流（即时/兼容）
                              |
                              v
                    SSDP 发现与可审计控制
~~~

本项目目前处于 Alpha 阶段。协议和安全行为有自动测试，但尚未对所有播放器、
设备本地导入协议和网络结构完成兼容性验证。

### 软路由上的能力与用户价值

| 软路由上的功能 | 给用户的实际效果 |
|---|---|
| 外部音源输入边界 | 用户自己的外部流程可提供合法取得的无损或高解析度文件，或白名单 URL。公共核心没有 provider 插件接口、账号或平台解析器，也没有音质契约。 |
| 完整下载与 SHA-256 内容寻址缓存 | 服务端声明 Content-Length 时，只有实际接收长度完全一致才发布缓存；无长度声明时则对实际接收字节计算摘要。这样可减少临时 URL 过期和重复下载的影响；核心不会隐式转码，但缓存本身不保证声音更好。 |
| device-local publisher 适配边界（推荐路径） | 设备适配器可以复制、校验并索引文件到播放器本地库，以使用设备更完整的本地播放路径。公共仓库只提供扩展接口，目前没有开箱即用的通用设备导入适配器。 |
| UPnP/OpenHome 推流（即时/兼容路径） | 无需先导入设备即可播放；字节透明、无转码且设备走相同解码路径时，同一文件可以不降质，但部分设备或桥接链路会受协议、格式和网络播放实现限制。 |
| SSDP 发现、正确切源与同设备意图控制 | 自动发现 renderer；OpenHome 先切到 Playlist 源再改队列；同设备操作串行，较新的播放或控制请求也会淘汰尚未落到设备的旧请求，避免较慢准备结果覆盖最后一次选择。 |
| 默认 6 小时令牌、来源白名单与 HTTP Range | 向播放器提供稳定的局域网地址，减少上游签名 URL 暴露，并支持播放器按区间读取音频。 |
| SQLite 与 LRU | 在软路由有限磁盘上复用缓存并限制容量。存储层虽有 pin 方法，但目前没有 CLI 或管理 API，不能作为开箱即用功能使用。 |
| 脱敏 health 与回环管理面 | `/health` 和 `/ready` 随媒体监听口在可信局域网内无鉴权提供；它们只返回最小状态，HTTP peer 只记不可逆短指纹。管理 API 仍强制只监听回环。 |
| OpenWrt/systemd 示例、CI 与发布审计 | 便于部署在软路由或常开 Linux 网关上，也便于维护、回滚和二次开发。 |

**推荐：优先设备本地播放；需要即时播放或设备不支持本地导入时使用
UPnP/OpenHome 推流。**

### 音质边界

当上游声明 Content-Length 时，LAN Music Bridge 能验证完整下载、SHA-256 内容、
来源边界和无隐式转码；上游未声明长度时，只能验证实际收到字节的摘要，不能证明
上游原本打算发送的总长度。项目不能承诺
所有设备都会“音质提升”。同一比特流经过相同解码和输出路径时，路由器缓存本身
不会天然改变声音。实际差异可能来自源文件版本、上游转码、传输协议、格式兼容、
播放器固件处理或设备本地播放实现。

音源选择与质量声明属于用户自己的外部音源流程；公共核心没有 provider 插件接口、
平台账号解析器或通用质量契约。设备本地导入同样需要单独安装并验证对应设备的
publisher adapter。

### 快速开始

要求 Python 3.11 或更高版本，并让软路由或 Linux 网关与播放器位于可互通的组播
网络。

~~~sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
install -d -m 0750 ./var/cache
cp config/config.example.toml ./config.toml
~~~

启动前请修改 config.toml。至少需要将 public_base_url 设置为播放器能够访问的网关
地址，并替换示例来源白名单。

~~~sh
lan-music-bridge --config ./config.toml validate-config
lan-music-bridge --config ./config.toml serve
~~~

在另一个终端中发现设备，并选择本地缓存路径或即时推流路径：

~~~sh
lan-music-bridge --config ./config.toml discover
lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode local --file ./track.flac \
  --content-type audio/flac
printf '%s\n' 'https://media.example/path/to/audio' | \
  lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode stream --url-stdin
~~~

mode local 会完整下载或读取文件并交给 publisher。默认 publisher 仍由网关提供缓存
文件；要导入播放器本地库，需配置经过审查的设备 adapter。mode stream 使用默认
6 小时、仅存内存的令牌代理允许的上游地址。stream 默认声明 `audio/mpeg`，local 文件默认按扩展名推断 MIME；
严格 renderer 可用 `--content-type` 显式指定。它只控制协议中的格式声明，不能判断
平台音质。通过标准输入传递临时媒体地址，可以避免它进入 Shell 历史。

运行测试和发布审计：

~~~sh
make check
make release-audit
~~~

### 安全与产品边界

媒体端口仅适合可信局域网；管理端口强制限制在回环地址。跨 VLAN、VPN、访客网络
或互联网开放端口前，请阅读[安全说明](SECURITY.md)。

公共核心没有 provider 插件接口，也不包含账号、平台解析、质量契约、设备存储凭据、
设备专有导入协议、固件、
媒体文件或部署配置。外部 adapter 是受信任代码，必须独立审查来源、许可证、权限、
日志脱敏、安装与回滚。详见[适配器说明](docs/ADAPTERS.md)。

本项目为独立开源软件，不代表任何设备厂商、平台或服务提供商的授权、认证、合作
关系或兼容性保证。

### 文档

- [架构](ARCHITECTURE.md)
- [安全说明](SECURITY.md)
- [适配器](docs/ADAPTERS.md)
- [Linux 安装、升级与回滚](docs/INSTALL-LINUX.md)
- [OpenWrt 打包](docs/INSTALL-OPENWRT.md)
- [私有扩展边界](docs/MIGRATION.md)
- [发布检查清单](docs/RELEASE.md)
- [源码来源](PROVENANCE.md)
- [更新记录](CHANGELOG.md)

本项目使用 Apache License 2.0 许可证。

---

## English

### Turn legally obtained audio into a stable, auditable LAN playback path

LAN Music Bridge runs on a router or always-on Linux gateway. It connects legally
obtained sources, verifiable caching, device-local publishing adapters, and renderer
control into one auditable LAN path. Prefer device-local playback; use
UPnP/OpenHome streaming when playback must start immediately or local import is not
supported.

Source version and quality, temporary download URLs, bridge protocol/format
capabilities, control sessions, and the renderer's actual playback path are usually
owned by different components. A failure at any layer can interrupt playback, select
the wrong file version, introduce an unnoticed transcode, or bypass a device's more
mature local decoding and playback implementation. Accounts, signed URLs, and
credentials must not enter logs or the public core.

Recommended path:

~~~text
your external source workflow (supplies a file or allow-listed URL)
              |
              v
complete download -> SHA-256 content-addressed cache
              |
              +-> device-local publisher adapter (preferred, device extension)
              |
              +-> UPnP/OpenHome streaming (immediate/compatible)
                              |
                              v
                    SSDP discovery and auditable control
~~~

The project is currently alpha. Protocol and security behavior has automated test
coverage, but compatibility has not been verified across every renderer,
device-local import protocol, or network layout.

### Gateway capabilities and user outcomes

| Capability on the gateway | Practical outcome for the user |
|---|---|
| External source-input boundary | Your own external workflow can supply a legally obtained lossless or high-resolution file, or an allow-listed URL. The public core has no provider plugin interface, account or platform resolver, or audio-quality contract. |
| Complete download and SHA-256 content-addressed cache | When a server declares Content-Length, a cache blob is published only if the received length matches exactly. Without a declared length, the digest covers the bytes actually received. This reduces the effect of expired temporary URLs and repeated downloads; the core does not transcode implicitly, but caching alone does not promise better sound. |
| Device-local publisher boundary (preferred path) | A device adapter can copy, verify, and index a file into the renderer's local library so its fuller local playback path can be used. The public repository provides the extension interface but no universal device-import adapter out of the box. |
| UPnP/OpenHome streaming (immediate/compatible path) | Start playback without importing first. The same file can remain lossless when delivery is byte-transparent, no transcode occurs, and the renderer uses the same decode path; some devices or bridges remain limited by protocol, format, or network-playback behavior. |
| SSDP discovery, correct source switching, and per-device intent control | Discover renderers, select the OpenHome Playlist source before queue mutation, serialize operations on one device, and let a newer play or control request supersede an older request that has not reached the renderer. |
| Six-hour default tokens, source allow-list, and HTTP Range | Give the renderer a stable LAN URL, reduce exposure of upstream signed URLs, and support ranged audio reads. |
| SQLite and LRU | Reuse cache storage on a capacity-constrained gateway and enforce a limit. The storage layer has a pin method, but there is no CLI or administration API for it, so pinning is not an out-of-the-box feature. |
| Redacted health and loopback administration | `/health` and `/ready` are unauthenticated on the media listener for trusted LAN use and return minimal state; HTTP peers are logged only as irreversible short fingerprints. The administration API remains loopback-only. |
| OpenWrt/systemd examples, CI, and release audits | Deploy on a router or always-on Linux gateway, then maintain, roll back, and extend it with auditable changes. |

**Recommendation: prefer device-local playback; use UPnP/OpenHome streaming for
immediate playback or when the device does not support local import.**

### Audio-quality boundary

When an upstream server declares Content-Length, LAN Music Bridge can verify a
complete download, SHA-256 content, source boundaries, and the absence of implicit
transcoding. Without a declared length it can verify only the digest of bytes actually
received, not the total the upstream intended to send. It cannot promise that every device will
sound better. When the same bitstream follows the same decoding and output path,
router caching does not inherently change the sound. Real differences can come from
the source-file version, upstream transcoding, transport protocol, format
compatibility, renderer firmware processing, or the device's local playback
implementation.

Source selection and quality declarations belong to your own external source
workflow. The public core has no provider plugin interface, platform account resolver,
or universal quality contract. Device-local import likewise requires a separately
installed and verified publisher adapter for that device.

### Quick start

Requirements: Python 3.11 or newer, with the router or Linux gateway and renderer on
a multicast-reachable network.

~~~sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
install -d -m 0750 ./var/cache
cp config/config.example.toml ./config.toml
~~~

Edit config.toml before starting. At minimum, set public_base_url to a gateway
address reachable by the renderer and replace the example source allow-list.

~~~sh
lan-music-bridge --config ./config.toml validate-config
lan-music-bridge --config ./config.toml serve
~~~

In another terminal, discover renderers and choose either the local-cache path or
the immediate-streaming path:

~~~sh
lan-music-bridge --config ./config.toml discover
lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode local --file ./track.flac \
  --content-type audio/flac
printf '%s\n' 'https://media.example/path/to/audio' | \
  lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode stream --url-stdin
~~~

mode local fully downloads or reads the file and passes it to the publisher. The
default publisher still serves the cached file from the gateway; importing into a
renderer library requires a reviewed device adapter. mode stream proxies an allowed
upstream URL through an in-memory token that expires after six hours. Stream mode declares `audio/mpeg` by default,
while local files infer MIME from their extension; use `--content-type` for a strict
renderer. This controls the protocol format declaration and does not determine source
quality. Passing a temporary media URL through stdin keeps it out of shell history.

Run the test and release gates with:

~~~sh
make check
make release-audit
~~~

### Security and product boundaries

The media listener is intended only for trusted LANs. The administration listener is
hard-limited to loopback. Read [SECURITY.md](SECURITY.md) before exposing a port
across a VLAN, VPN, guest network, or the internet.

The public core has no provider plugin interface and does not include accounts,
platform resolution, a quality contract, device-storage credentials, proprietary
device-import protocols, firmware, media,
or deployment configuration. External adapters are trusted code and require their
own provenance, license, permission, log-redaction, installation, and rollback
review. See [docs/ADAPTERS.md](docs/ADAPTERS.md).

This independent project does not claim authorization, certification, partnership,
or compatibility guarantees from any device vendor, platform, or service provider.

### Documentation

- [Architecture](ARCHITECTURE.md)
- [Security](SECURITY.md)
- [Adapters](docs/ADAPTERS.md)
- [Linux installation and rollback](docs/INSTALL-LINUX.md)
- [OpenWrt packaging](docs/INSTALL-OPENWRT.md)
- [Private extension boundary](docs/MIGRATION.md)
- [Release checklist](docs/RELEASE.md)
- [Source provenance](PROVENANCE.md)
- [Changelog](CHANGELOG.md)

Licensed under Apache License 2.0.
