# Nook (`nk`)

[English](./README.md)

> 为终端重度用户准备的 SSH jumpbox。

`Nook` 是一个更像“正式产品”的 SSH 服务器书签工具。它保留了单文件 Bash 工具的轻量特性，同时把品牌、交互体验、诊断能力和开源项目表面都整理到了一个更专业的状态。

## 为什么用 Nook

- 主命令简洁稳定：`nk`
- `fzf` 驱动的交互式服务器选择器
- 支持服务器分组、备注和最近使用置顶
- 内置 SSH 免密配置和连通性检测
- 自动从 `~/.ssh-manager` 迁移到 `~/.config/nook`
- 提供 `nk doctor` 诊断命令，方便排查环境问题

## 快速开始

```bash
curl -fsSL https://raw.githubusercontent.com/guyfar/nook-ssh/main/install.sh | bash
nk add
nk
```

默认配置目录：

```text
~/.config/nook/
```

如果检测到旧版 `~/.ssh-manager/` 配置，Nook 会自动导入。

## 使用体验

Nook 不是简单地把 SSH 地址堆在一个脚本里，而是把常用流程收成一套更顺手的终端体验：

- 带品牌感的 TUI 选择器和预览面板
- 最近使用的服务器自动排在前面
- 密码登录和密钥登录统一管理
- 配置文件保持纯文本，可读、可备份、可版本管理

## 命令

| 命令 | 功能 |
|------|------|
| `nk` | 打开交互式选择器 |
| `nk add` | 添加服务器 |
| `nk rm` | 删除服务器 |
| `nk list` | 列出服务器 |
| `nk edit` | 编辑配置 |
| `nk key` | 配置 SSH 免密 |
| `nk ping` | 检测连通性 |
| `nk doctor` | 输出诊断信息 |
| `nk <关键词>` | 搜索并连接 |
| `nk help` | 显示帮助 |

## 配置

默认配置文件：

```text
~/.config/nook/servers.conf
```

自定义配置目录：

```bash
export NOOK_CONFIG_DIR=/path/to/custom-config-dir
```

配置格式：

```conf
# Format : name | host | port | user | password(optional) | description

[production]
# prod-web-01 | 1.2.3.4 | 22   | root | yourpass  | production web node
# prod-web-02 | 1.2.3.5 | 22   | root |           | production web node 2
# prod-db-01  | 1.2.3.6 | 3306 | root | dbpass123 | primary database
```

密码留空时表示使用 SSH 密钥登录。

## 免密配置

```bash
nk key
```

Nook 会自动检测本地公钥；如果没有，会生成 `ed25519` 密钥并通过 `ssh-copy-id` 下发到目标服务器。

## 依赖

- `bash` 4.0+
- `fzf` 可选但强烈推荐
- `sshpass` 可选，仅密码登录时需要

## 诊断

```bash
nk doctor
```

它会输出版本、配置路径、服务器数量，以及 `ssh` / `fzf` / `sshpass` 的可用性，便于定位安装和连接问题。

## 开发

```bash
bash -n nk install.sh
./nk help
NOOK_INSTALL_DIR=/tmp/nook-bin XDG_CONFIG_HOME=/tmp/nook-xdg bash ./install.sh
```

项目协作与发布说明见：

- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `RELEASE_CHECKLIST.md`

## License

MIT
