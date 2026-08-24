# SPDX-License-Identifier: Apache-2.0
include $(TOPDIR)/rules.mk

PKG_NAME:=lan-music-bridge
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
PKG_LICENSE:=Apache-2.0
PKG_LICENSE_FILES:=LICENSE NOTICE
PKG_MAINTAINER:=LAN Music Bridge contributors

include $(INCLUDE_DIR)/package.mk

SOURCE_DIR?=$(CURDIR)/../..

define Package/lan-music-bridge
  SECTION:=utils
  CATEGORY:=Utilities
  TITLE:=Vendor-neutral UPnP/OpenHome music bridge
  DEPENDS:=+python3-light +python3-urllib +python3-sqlite3 +ca-bundle
endef

define Package/lan-music-bridge/description
 Discovers and controls LAN renderers, proxies allow-listed streams, and serves
 content-addressed local media without provider-specific dependencies.
endef

define Build/Prepare
	$(RM) -r $(PKG_BUILD_DIR)
	$(INSTALL_DIR) $(PKG_BUILD_DIR)
	$(CP) $(SOURCE_DIR)/src/lan_music_bridge $(PKG_BUILD_DIR)/
	$(CP) $(SOURCE_DIR)/LICENSE $(SOURCE_DIR)/NOTICE $(PKG_BUILD_DIR)/
endef

define Build/Compile
endef

define Package/lan-music-bridge/conffiles
/etc/config/lan-music-bridge
/etc/lan-music-bridge/config.toml
endef

define Package/lan-music-bridge/install
	$(INSTALL_DIR) $(1)/usr/libexec/lan-music-bridge
	$(CP) $(PKG_BUILD_DIR)/lan_music_bridge $(1)/usr/libexec/lan-music-bridge/
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/etc/init.d/lan-music-bridge $(1)/etc/init.d/lan-music-bridge
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/etc/config/lan-music-bridge $(1)/etc/config/lan-music-bridge
	$(INSTALL_DIR) $(1)/etc/lan-music-bridge
	$(INSTALL_CONF) $(SOURCE_DIR)/config/config.example.toml $(1)/etc/lan-music-bridge/config.toml
endef

$(eval $(call BuildPackage,lan-music-bridge))
