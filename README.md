# 黄金价格监控系统

实时获取上海黄金交易所 Au9999 价格，当价格涨或跌超过设定阈值时，通过 QQ 邮箱发送通知。

## 功能特点

- **实时金价获取**: 上海黄金交易所 Au9999 实时价格（金投网 + 东方财富双数据源，自动切换）
- **简单波动监控**: 记录当日最高最低价，涨跌超过阈值即通知
- **邮件通知**: QQ 邮箱 SMTP 发送 HTML 格式通知邮件
- **持续行情捕捉**: 触发通知后更新基准价格，持续单边行情可多次通知
- **跨天自动重置**: 每日自动重置高低价记录
- **完善日志系统**: 支持日志轮转，方便问题排查
- **Docker 支持**: 一键容器化部署
- **环境变量配置**: 支持环境变量覆盖敏感信息，适配云平台部署

## 监控算法

系统采用简单直观的价格波动监控逻辑：

1. 程序启动后持续采集金价（默认每 40 秒一次）
2. 自动记录当天的**最高价**和**最低价**
3. 当价格相比基准高点**下跌 ≥ 阈值**（默认 5 元/克）→ 发送跌幅通知
4. 当价格相比基准低点**上涨 ≥ 阈值**（默认 5 元/克）→ 发送涨幅通知
5. 触发通知后，以当前价格作为新的基准，避免重复通知

**示例**：

```
时间:   09:00  10:00  11:00  12:00  13:00
价格:    680    685    688    682    694
                             ↑ 从688跌到682，跌6 → 通知
                                    ↑ 从682涨到694，涨12 → 通知
```

## 环境要求

- Python 3.8+
- 网络连接（用于获取实时金价）
- QQ 邮箱（需开启 SMTP 服务）

## 快速开始

### 1. 克隆项目

```bash
git clone <repository_url>
cd golden
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置

复制示例配置文件并填写邮箱信息：

```bash
cp config/config.yaml.example config/config.yaml
```

编辑 `config/config.yaml`，填写邮箱配置：

```yaml
email:
  sender: your_qq@qq.com        # 你的QQ邮箱
  password: your_auth_code      # QQ邮箱授权码(非登录密码)
  receivers:
    - target@qq.com             # 接收通知的邮箱
```

**获取 QQ 邮箱授权码**：
1. 登录 [QQ 邮箱网页版](https://mail.qq.com)
2. 点击 **设置** → **账户**
3. 找到 **POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV 服务**
4. 点击 **开启服务**（可能需要短信验证）
5. 生成授权码并复制到配置文件的 `password` 字段

### 4. 运行

```bash
python main.py
```

## Docker 部署

```bash
# 构建镜像
docker build -t golden .

# 运行（挂载配置文件）
docker run -d --name golden \
  --restart=always \
  -v ./config/config.yaml:/app/config/config.yaml \
  -v ./logs:/app/logs \
  golden
```

也可以通过环境变量传递邮件配置（无需挂载配置文件）：

```bash
docker run -d --name golden \
  --restart=always \
  -e EMAIL_SENDER=your_qq@qq.com \
  -e EMAIL_PASSWORD=your_auth_code \
  -e EMAIL_RECEIVERS=target@qq.com \
  golden
```

## 云平台部署

项目支持部署到 Render、Railway 等云平台。以 Render 为例：

1. 将代码推送到 GitHub
2. 在 [Render](https://render.com) 创建 **Background Worker**，关联仓库
3. Runtime 选择 **Docker**，Instance 选择 **Free**
4. 添加环境变量：`EMAIL_SENDER`、`EMAIL_PASSWORD`、`EMAIL_RECEIVERS`
5. 完成，自动部署运行

## 项目结构

```
golden/
├── main.py                      # 程序入口
├── requirements.txt             # 依赖清单
├── Dockerfile                   # Docker 构建文件
├── .gitignore                   # Git 忽略规则
├── config/
│   ├── config.yaml.example      # 配置文件示例
│   └── config.yaml              # 实际配置文件（不入库）
├── src/
│   ├── __init__.py
│   ├── data_fetcher.py          # 数据获取模块（金投网 + 东方财富双数据源）
│   ├── price_algorithm.py       # 价格波动算法模块
│   ├── signal_generator.py      # 技术指标信号模块（保留备用）
│   ├── email_notifier.py        # 邮件通知模块
│   └── scheduler.py             # 定时调度模块
├── tests/
│   ├── __init__.py
│   ├── test_price_algorithm.py  # 价格算法单元测试
│   └── test_signal.py           # 技术指标单元测试
├── logs/                        # 日志目录（自动生成）
└── data/                        # 数据目录
```

## 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| api.interval | 采集间隔（秒） | 40 |
| api.timeout | 请求超时（秒） | 10 |
| api.retry_times | 请求重试次数 | 3 |
| algorithm.threshold | 波动通知阈值（元/克） | 5 |
| algorithm.cooldown | 通知冷却时间（秒） | 600 |
| email.sender | 发件人 QQ 邮箱 | - |
| email.password | QQ 邮箱授权码 | - |
| email.receivers | 收件人邮箱列表 | - |
| logging.level | 日志级别 | INFO |

## 运行测试

```bash
python -m unittest discover tests -v
```

## 常见问题

### Q: 程序启动后多久会收到邮件？

A: 取决于金价波动。程序会立即开始监控，当价格涨或跌超过阈值（默认 5 元/克）时发送邮件。如果金价波动平稳，可能较长时间不会触发通知。

### Q: 如何调整通知灵敏度？

修改 `config/config.yaml` 中的阈值：
```yaml
algorithm:
  threshold: 3    # 改小更灵敏，改大更保守
```

### Q: 收不到邮件怎么办？

1. 检查 `logs/app.log` 查看错误信息
2. 确认 QQ 邮箱授权码正确（不是登录密码）
3. 确认 SMTP 服务已开启
4. 检查邮件是否被收件方当作垃圾邮件

### Q: 数据获取失败怎么办？

系统内置重试机制和双数据源自动切换（金投网 → 东方财富），如果持续失败请检查网络连接。

## 注意事项

- 通知冷却期内不会重复发送邮件（默认 10 分钟）
- 每日自动重置高低价记录
- **风险提示**: 价格提醒仅供参考，不构成投资建议，投资有风险，决策需谨慎

## 许可证

MIT License
