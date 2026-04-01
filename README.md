# Goofish Rent Watcher

面向闲鱼/Goofish 转租场景的浏览器自动化监控工具。

这个仓库优先服务中文使用者，但同时保留英文说明给外部开发者参考：
[README.en.md](./README.en.md)

## 项目定位

这个项目的目标不是做一个通用租房平台 SDK，而是提供一个能实际跑起来的监控脚本：

- 使用可见浏览器完成登录和搜索
- 按关键词、价格、附近地点等条件筛选
- 记录已见过的房源，减少重复提醒
- 输出适合人看和适合程序消费的两种结果

当前版本更偏“实用脚本”而不是“高稳定产品”，所以你应该预期：

- 页面结构变化会导致脚本失效
- 不同机器和浏览器环境可能需要微调
- 目前实际验证最充分的是 macOS

## 环境要求

- Python 3.11+
- 可运行桌面浏览器的环境
- 能访问闲鱼/Goofish
- 已安装 Playwright 相关浏览器依赖

说明：

- 当前仓库主要在 macOS 环境下验证过
- Linux / Windows 理论上可以运行，但目前没有完整验证
- 某些 macOS 环境下，Playwright 自带 Chromium 可能不稳定，此时建议配置本机 Chrome 路径

## 快速开始

推荐首次使用流程：

1. 执行一键初始化
2. 修改一次 `.env`
3. 执行环境检查
4. 扫码登录
5. 开始检查

一键初始化：

```bash
make setup
```

这一步会自动完成：

- 创建 `.venv`
- 安装 Python 依赖
- 安装 Playwright Chromium
- 根据 `.env.example` 生成 `.env`
- 执行一次 `env-check`

然后编辑 `.env`，至少改这些字段：

```dotenv
GOOFISH_MIN_PRICE=1500
GOOFISH_MAX_PRICE=2600
GOOFISH_NEARBY_RADIUS_KM=10
GOOFISH_NEARBY_LOCATION=你自己的小区、地标或地址文本
```

再执行：

```bash
make env-check
python3 -m goofish_rent capture-state
python3 -m goofish_rent check
```

## 配置说明

项目会自动读取仓库根目录下的 `.env`。

可用环境变量如下：

| 变量名 | 默认值 | 说明 |
| --- | --- | --- |
| `GOOFISH_SEARCH_KEYWORD` | `转租` | 搜索关键词 |
| `GOOFISH_MIN_PRICE` | `1800` | 最低价格 |
| `GOOFISH_MAX_PRICE` | `2400` | 最高价格 |
| `GOOFISH_NEARBY_RADIUS_KM` | `5` | 附近搜索半径 |
| `GOOFISH_NEARBY_LOCATION` | `示例地址` | 附近搜索地点 |
| `GOOFISH_SORT_MODE` | `latest` | 当前基线上下文用到的排序标记 |
| `GOOFISH_CHROME_PATH` | 空 | 可选，本机 Chrome 可执行文件路径 |

如果你在 macOS 上遇到 Playwright Chromium 启动不稳定，可以在 `.env` 里加：

```dotenv
GOOFISH_CHROME_PATH=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
```

## 环境检查

首次运行前建议先执行：

```bash
make env-check
```

等价命令：

```bash
python3 -m goofish_rent env-check
```

这个命令会检查：

- 当前 Python 版本
- `playwright` 是否已安装
- 当前将使用哪个浏览器路径
- 当前生效的搜索配置
- 是否存在阻塞运行的问题

## 常用命令

初始化配置文件：

```bash
python3 -m goofish_rent init-config
```

扫码登录并保存登录态：

```bash
python3 -m goofish_rent capture-state
```

执行一次检查：

```bash
python3 -m goofish_rent check
```

输出 JSON：

```bash
python3 -m goofish_rent check --json
```

使用稳定 JSON 接口：

```bash
python3 -m goofish_rent skill-check
```

可选：导入导出的 cookies / storage_state：

```bash
python3 -m goofish_rent import-state /path/to/cookies.json
```

## 输出说明

`check` 在发现新房源时，文本输出类似：

```text
整租一居室 | ¥3200/月 | 某区域 | https://www.goofish.com/...
合租次卧 | ¥1800/月 | 某区域 | https://www.goofish.com/...
```

没有新房源时：

```text
暂无新的符合条件的租房信息
```

`skill-check` 输出的 JSON 示例：

```json
{"status":"new_items_found","notify":true,"message":"发现 2 条新的符合条件的租房信息","items":[{"item_id":"123","title":"整租一居室","price":"¥3200/月","area":"某区域","url":"https://www.goofish.com/item?id=123"}]}
```

可能状态包括：

- `initialized`
- `no_new_items`
- `new_items_found`
- `needs_login`
- `error`

## 运行产物

以下目录和文件是运行时生成的，本仓库默认不会提交：

- `auth/browser_profile/`：浏览器登录 profile
- `auth/storage_state.json`：浏览器存储快照
- `auth/session_storage.json`：session storage 快照
- `auth/auth_metadata.json`：非敏感的登录元信息
- `data/latest_results.json`：最近一次抓取结果
- `data/seen_item_ids.json`：历史已见房源 ID
- `others/`：调试截图和其他临时文件

## 隐私与发布注意事项

- 不要提交 `auth/`、`data/`、`others/` 下的真实运行数据
- 不要把自己的真实关注地址写进 README 或示例配置
- 导入登录态后，元数据里只会记录源文件名，不记录绝对路径
- 如果你有私有自动化脚本或本地工具集成，建议放在仓库外维护

## 测试

执行：

```bash
make test
```

等价命令：

```bash
python3 -m unittest discover -s tests -p 'test*.py' -q
```

当前测试主要覆盖：

- URL / item_id 处理逻辑
- 部分 CLI JSON 输出行为
- 配置初始化和环境检查

当前不覆盖真实浏览器端到端流程。

## 已知限制

- 闲鱼页面结构一旦变化，脚本可能失效
- 这个流程依赖可见浏览器，headless 模式不可靠
- “附近”筛选逻辑对页面 UI 结构较敏感
- `GOOFISH_SORT_MODE` 目前更多用于基线上下文标记，而不是完整驱动 UI 排序

## 英文文档

如果你需要英文版说明，请查看：
[README.en.md](./README.en.md)
