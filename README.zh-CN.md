# Nook (`nk`)

[English](./README.md)

保存 SSH 服务器，搜索后回车连接。单文件 Bash 工具，支持分组、备注和最近使用排序。

## 快速开始

```bash
curl -fsSL https://raw.githubusercontent.com/guyfar/nook-ssh/main/install.sh | bash
nk add
nk
```

添加时只需输入地址和名称。地址可以是 `ubuntu@example.com`，也可以粘贴 `ssh ubuntu@example.com -p 2222`。默认端口为 `22`，省略用户名时沿用 `root`。

也可以直接传入地址，再确认名称：

```bash
nk add ubuntu@example.com
nk add 'ssh ubuntu@example.com -p 2222'
```

支持 `[user@]host`、IPv6，以及 `-p` 和 `-l` 参数。其他 SSH 参数和远程命令会明确报错，不会执行粘贴的命令。

在终端中填错地址、端口或名称时，只需重填对应字段，其他输入会保留。通过管道提供输入时，遇到错误会直接退出，不会把后续内容当作修正值。

## 日常使用

- `nk`：搜索名称、地址、用户名、分组或备注；最近使用的服务器优先展示。
- `nk 名称`：名称完全匹配且唯一时直接连接；否则打开选择器。
- 选择器中按 **Enter** 连接、**Tab** 展开或收起详情、**ctrl-r** 刷新状态、**Esc** 取消。
- 选择器里的操作都作用于当前高亮服务器：**Enter** 连接、**ctrl-k** 配置免密登录、**ctrl-p** 检查连通性、**ctrl-y** 复制 SSH 命令、**ctrl-e** 查看完整详情、**ctrl-d** 删除。
- 这些操作都在选择器内完成：详情显示在预览面板，ping 或删除后列表会原地刷新。提示栏会根据终端宽度自适应。
- 列表按名称、分组、完整的 `用户@地址:端口`、备注、上次连接距今时间和连通状态展示。详情额外提供登录方式和可手动执行的 SSH 命令，按 **Alt+↑/↓** 滚动查看。
- 状态来自上一次 `nk ping`，启动时不会主动探测，因此选择器始终很快；末尾的 `*` 表示该结果已超过一小时。在选择器中按 **ctrl-r**，或运行 `nk ping`，即可刷新。
- 在终端里连接失败时，Nook 会给出修复菜单（`p` 检查端口、`k` 配置免密、`e` 编辑、`c` 复制命令），而不是直接退出。
- 未安装 `fzf` 时，用编号选择；直接回车取消。
- 首次在终端运行 `nk`，没有服务器时直接进入添加流程。

默认由 SSH 处理密钥、ssh-agent 或密码输入，无需先保存密码。

需要分组、备注或保存密码时使用：

```bash
nk add --advanced
```

保存的密码以明文写入本地配置，文件权限为 `600`。自动填写保存的密码需要 `sshpass`；未安装时使用普通 SSH 登录。

## 其他命令

| 命令 | 功能 |
|------|------|
| `nk list` | 列出服务器，含上次连接时间与状态 |
| `nk rm` | 选择并确认删除服务器 |
| `nk edit` | 使用 `$EDITOR` 编辑配置，默认为 Vim |
| `nk key` | 选择服务器，配置 SSH 免密登录 |
| `nk ping` | 检查服务器端口连通性 |
| `nk doctor` | 查看环境诊断 |
| `nk version` | 显示版本 |
| `nk help` | 显示帮助 |

`nk ping` 检查本机到配置地址和端口的直接 TCP 连通性，不代表 SSH 登录成功，也不经过 SSH 跳板或代理。缺少 `nc` 会直接提示；任一端口不可达时返回非零状态。结果会缓存并显示在选择器和 `nk list` 中，直到下次检查。

`nk key` 失败时保留 SSH 的原始错误和退出状态，并给出用于核对登录的命令。

## 配置

默认文件为 `~/.config/nook/servers.conf`，支持 `XDG_CONFIG_HOME`，也可单独覆盖：

```bash
export NOOK_CONFIG_DIR=/path/to/custom-config-dir
```

配置格式保持不变：

```conf
# name | host | port | user | password(optional) | description
[production]
web-prod | 192.0.2.10 | 22 | ubuntu | | production web server
```

新增名称必须唯一，端口范围为 `1–65535`，字段不能包含 `|`、制表符或换行。手动编辑后的无效条目会提示文件位置，不会静默跳过。已有同名条目仍需手动选择，不会直接连接。

检测到旧版 `~/.ssh-manager/` 时自动迁移；设置 `NOOK_CONFIG_DIR` 后不自动迁移。

## 依赖与开发

- Bash 3.2+、OpenSSH，以及常见 Unix 命令。
- `fzf`：可选，用于交互式搜索。
- `column`：可选，用于对齐列表列和中文名称；缺少时仍可正常选择和连接。
- `sshpass`：可选，用于自动填写保存的密码。
- `ssh-copy-id`：仅配置免密登录时需要；`nc`：仅连通性检查时需要。

```bash
bash -n nk install.sh
python3 -m unittest discover -s tests -v
./nk help
./nk doctor
```

测试使用临时配置和模拟 SSH 命令，不连接真实服务器。Python 仅用于测试，日常使用不需要。

协作与发布流程见 [CONTRIBUTING.md](./CONTRIBUTING.md) 和 [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md)。

## License

MIT
