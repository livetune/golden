# 黄金价格监控系统

实时获取黄金价格，通过MA均线、RSI、MACD技术指标分析，生成买入信号并通过QQ邮箱发送通知。

## 功能特点

- **实时金价获取**: 上海黄金交易所Au9999实时价格（东方财富数据源）
- **技术指标分析**: MA20均线、RSI(14)、MACD(12,26,9)三重指标
- **智能买入信号**: 至少满足2个指标条件时触发
- **邮件通知**: 通过QQ邮箱SMTP发送美观的HTML格式通知
- **历史数据存储**: 自动保存价格数据到本地CSV文件
- **完善日志系统**: 支持日志轮转，方便问题排查

## 环境要求

- Python 3.8+
- 网络连接（用于获取实时金价）
- QQ邮箱（需开启SMTP服务）

## 快速开始

### 1. 克隆项目

```bash
git clone <repository_url>
cd golden
```

### 2. 创建虚拟环境（推荐）

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置邮箱

编辑 `config/config.yaml`，填写QQ邮箱配置：

```yaml
email:
  smtp_server: smtp.qq.com
  smtp_port: 465
  use_ssl: true
  sender: your_qq@qq.com        # 你的QQ邮箱
  password: your_auth_code      # QQ邮箱授权码(非登录密码)
  receivers:
    - target@qq.com             # 接收通知的邮箱
```

**获取QQ邮箱授权码**:
1. 登录 [QQ邮箱网页版](https://mail.qq.com)
2. 点击顶部 **设置** -> **账户**
3. 向下滚动找到 **POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务**
4. 点击 **开启服务**（可能需要短信验证）
5. 生成授权码并复制到配置文件的 `password` 字段

### 5. 运行程序

```bash
python main.py
```

## 技术指标说明

### MA (移动平均线)

移动平均线是最基础的趋势跟踪指标，通过计算过去N个周期的平均价格来平滑价格波动。

- **周期**: 20（可在配置文件修改）
- **买入信号**: 价格从下方突破MA20，或价格在MA上方且MA斜率向上

### RSI (相对强弱指数)

RSI衡量价格变动的速度和幅度，范围0-100。

- **周期**: 14
- **超卖阈值**: 30（低于此值表示超卖）
- **超买阈值**: 70（高于此值表示超买）
- **买入信号**: RSI低于30进入超卖区域，或从超卖区域开始回升

### MACD (指数平滑异同移动平均线)

MACD是趋势跟踪动量指标，由DIF线、DEA线和柱状图组成。

- **快线周期**: 12
- **慢线周期**: 26
- **信号线周期**: 9
- **买入信号**: DIF从下方突破DEA形成金叉，或MACD柱状图由负转正

## 买入信号逻辑

当满足以下条件中的**至少2个**时，触发买入信号：

| 指标 | 买入条件 | 说明 |
|------|----------|------|
| MA均线 | 价格上穿MA20 或 价格>MA且MA上升 | 趋势确认 |
| RSI | RSI < 30 或 RSI从超卖区域回升 | 超卖反弹 |
| MACD | DIF上穿DEA 或 MACD柱>0且增大 | 动量确认 |

**信号冷却机制**: 触发信号后1小时内不会重复发送（可配置），避免频繁打扰。

## 项目结构

```
golden/
├── main.py                  # 程序入口
├── requirements.txt         # 依赖清单
├── README.md               # 项目文档
├── config/
│   └── config.yaml         # 配置文件（需修改邮箱信息）
├── src/
│   ├── __init__.py
│   ├── data_fetcher.py     # 数据获取模块 - 从新浪财经API获取金价
│   ├── signal_generator.py # 信号生成模块 - 计算技术指标并生成信号
│   ├── email_notifier.py   # 邮件通知模块 - 发送HTML格式邮件
│   └── scheduler.py        # 定时调度模块 - 每分钟执行任务
├── tests/
│   ├── __init__.py
│   └── test_signal.py      # 单元测试
├── logs/                   # 日志目录（自动生成）
│   └── app.log            # 运行日志
└── data/                   # 数据目录（自动生成）
    └── gold_prices.csv    # 历史价格数据
```

## 完整配置说明

| 配置项 | 说明 | 默认值 | 可选值 |
|--------|------|--------|--------|
| api.source | 数据源 | eastmoney | 上金所Au9999 |
| api.interval | 采集间隔(秒) | 60 | 30-300 |
| api.timeout | 请求超时(秒) | 10 | 5-30 |
| api.retry_times | 重试次数 | 3 | 1-5 |
| indicators.ma_period | MA周期 | 20 | 5-60 |
| indicators.rsi_period | RSI周期 | 14 | 6-24 |
| indicators.rsi_oversold | RSI超卖阈值 | 30 | 20-40 |
| indicators.rsi_overbought | RSI超买阈值 | 70 | 60-80 |
| indicators.macd_fast | MACD快线周期 | 12 | 8-15 |
| indicators.macd_slow | MACD慢线周期 | 26 | 20-30 |
| indicators.macd_signal | MACD信号线周期 | 9 | 6-12 |
| signal.min_conditions | 触发信号的最少条件数 | 2 | 1-3 |
| signal.cooldown | 信号冷却时间(秒) | 3600 | 300-7200 |
| logging.level | 日志级别 | INFO | DEBUG/INFO/WARNING/ERROR |
| logging.max_bytes | 单个日志文件大小 | 10MB | - |
| logging.backup_count | 保留日志文件数 | 5 | 1-10 |

## 使用示例

### 后台运行 (Linux/macOS)

```bash
nohup python main.py > /dev/null 2>&1 &
```

### 后台运行 (Windows)

```powershell
# 使用PowerShell
Start-Process -WindowStyle Hidden python -ArgumentList "main.py"

# 或创建Windows计划任务
```

### 使用systemd服务 (Linux)

创建 `/etc/systemd/system/gold-monitor.service`:

```ini
[Unit]
Description=Gold Price Monitor
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/golden
ExecStart=/path/to/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务:
```bash
sudo systemctl daemon-reload
sudo systemctl enable gold-monitor
sudo systemctl start gold-monitor
```

## 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行指定测试
python -m pytest tests/test_signal.py -v

# 生成覆盖率报告
python -m pytest tests/ --cov=src --cov-report=html
```

## 常见问题

### Q: 程序启动后多久会收到第一封邮件？

A: 系统需要积累至少26条数据点（约26分钟）才能开始计算MACD指标。之后当满足买入条件时才会发送邮件。

### Q: 收不到邮件怎么办？

1. 检查 `logs/app.log` 查看错误信息
2. 确认QQ邮箱授权码正确（不是登录密码）
3. 确认SMTP服务已开启
4. 检查邮件是否被收件方当作垃圾邮件

### Q: 如何修改触发条件的灵敏度？

- **更灵敏**: 将 `signal.min_conditions` 改为1
- **更保守**: 将 `signal.min_conditions` 改为3
- **调整RSI阈值**: 超卖阈值从30改为35会更容易触发

### Q: 数据获取失败怎么办？

系统内置重试机制（默认3次），如果持续失败请检查：
1. 网络连接是否正常
2. 新浪财经API是否可访问
3. 查看日志中的具体错误信息

### Q: 如何只接收邮件而不看控制台输出？

修改 `config/config.yaml` 中的日志级别:
```yaml
logging:
  level: WARNING  # 只显示警告和错误
```

## 注意事项

- 系统启动后需要积累至少26条数据才能开始分析
- 信号冷却期内不会重复发送邮件
- 数据保存在 `data/gold_prices.csv`，可用于回测分析
- **风险提示**: 买入信号仅供参考，不构成投资建议，投资有风险，决策需谨慎

## 后续优化方向

- [x] 支持多数据源自动切换（已支持新浪、Yahoo Finance）
- [ ] 添加卖出信号分析
- [ ] Web界面实时展示
- [ ] 支持微信/钉钉通知
- [ ] 添加回测功能
- [ ] 支持多品种监控（白银、原油等）

## 许可证

MIT License
