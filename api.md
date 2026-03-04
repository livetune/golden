# 国内黄金（T+D）可用接口汇总

本文档整理了获取国内黄金T+D行情数据的主要API接口，包括免费和付费方案。

---

## 一、免费开源库（推荐）

### 1. AKShare

**官网**: https://akshare.akfamily.xyz/

**简介**: AKShare 是完全开源且免费的 Python 金融数据接口库，数据源涵盖上海黄金交易所、东方财富、新浪财经等多个平台。

**安装**:
```bash
pip install akshare
```

**核心接口**:

#### 1.1 获取上海黄金交易所历史行情数据
```python
import akshare as ak

# 获取 Au(T+D) 黄金T+D历史行情
spot_hist_sge_df = ak.spot_hist_sge(symbol='Au(T+D)')
print(spot_hist_sge_df)

# 获取白银T+D历史行情
silver_df = ak.spot_hist_sge(symbol='Ag(T+D)')
print(silver_df)
```

**返回字段**:
| 字段名 | 类型 | 描述 |
|--------|------|------|
| date | object | 日期 |
| open | float64 | 开盘价 |
| close | float64 | 收盘价 |
| high | float64 | 最高价 |
| low | float64 | 最低价 |

#### 1.2 获取上海金基准价
```python
import akshare as ak

# 获取上海金基准价历史数据
spot_golden_benchmark_sge_df = ak.spot_golden_benchmark_sge()
print(spot_golden_benchmark_sge_df)
```

**返回字段**:
| 字段名 | 描述 |
|--------|------|
| 交易时间 | 日期 |
| 晚盘价 | 晚盘基准价 |
| 早盘价 | 早盘基准价 |

#### 1.3 获取品种列表
```python
import akshare as ak

# 获取上海黄金交易所所有品种列表
symbol_list = ak.spot_symbol_list_sge()
print(symbol_list)
```

**支持的主要品种**:
- `Au(T+D)` - 黄金T+D
- `Ag(T+D)` - 白银T+D
- `mAu(T+D)` - 迷你黄金T+D
- `Au99.99` - 黄金9999
- `Au99.95` - 黄金9995
- `Au100g` - 金条100g
- `iAu99.99` - 国际板黄金

**优点**:
- 完全免费，无调用次数限制
- 数据来源权威（直接抓取上海黄金交易所官网）
- 返回 Pandas DataFrame，便于分析处理
- 开源项目，持续更新维护

---

### 2. Tushare

**官网**: https://tushare.pro/

**简介**: 国内知名的金融数据接口库，提供股票、期货、基金等数据。基础功能免费，高级功能需要积分。

**安装**:
```bash
pip install tushare
```

**注意**: Tushare 主要提供股票和期货数据，对于黄金T+D现货数据支持有限，建议使用 AKShare。

---

## 二、商业API接口

### 1. 聚合数据 - 黄金行情API

**官网**: https://www.juhe.cn/docs/api/id/29

**简介**: 提供黄金品种、最新价、开盘价、最高价等信息查询服务。

**价格方案**:
| 套餐 | 价格 | 调用次数 |
|------|------|----------|
| 普通会员 | 免费 | 50次/天 |
| 黑钻会员 | ¥1299 | 10000次/天 |
| 黑钻PLUS | ¥3999 | 无限次/天 |

**请求示例**:
```python
import requests

url = "http://web.juhe.cn/finance/gold/shgold"
params = {
    "key": "您的API密钥",
    "v": ""
}
response = requests.get(url, params=params)
data = response.json()
print(data)
```

**返回字段**:
| 字段名 | 描述 |
|--------|------|
| variety | 品种代码 |
| varietynm | 品种名称 |
| last_price | 最新价 |
| buy_price | 买入价 |
| sell_price | 卖出价 |
| open_price | 开盘价 |
| high_price | 最高价 |
| low_price | 最低价 |
| change_percent | 涨跌幅 |

**错误码**:
- `202901`: 查询不到结果
- `202902`: 参数错误
- `10001`: 错误的请求KEY

---

### 2. 极速数据 - 黄金价格API

**官网**: https://www.jisuapi.com/api/gold/

**简介**: 提供上海黄金交易所、上海期货交易所、香港金银业贸易场、银行账户黄金等多市场数据。

**价格方案**:
| 套餐 | 调用次数 |
|------|----------|
| 免费会员 | 100次/天 |
| 白银会员 | 600次/天 |
| 钻石会员 | 15万次/日 |

**接口列表**:

#### 2.1 上海黄金交易所价格
```
GET https://api.jisuapi.com/gold/shgold?appkey=您的appkey
```

#### 2.2 上海期货交易所价格
```
GET https://api.jisuapi.com/gold/shfutures?appkey=您的appkey
```

**请求示例 (Python)**:
```python
import requests

url = "https://api.jisuapi.com/gold/shgold"
params = {"appkey": "您的appkey"}

response = requests.get(url, params=params)
data = response.json()

if data["status"] == 0:
    for item in data["result"]:
        print(f"{item['typename']}: {item['price']} 元/克")
```

**返回示例**:
```json
{
    "status": 0,
    "msg": "ok",
    "result": [
        {
            "type": "Au(T+D)",
            "typename": "黄金延期",
            "price": "1070.00",
            "openingprice": "1065.00",
            "maxprice": "1075.50",
            "minprice": "1060.00",
            "changepercent": "-2.30%",
            "updatetime": "2026-02-06 15:30:00"
        }
    ]
}
```

**错误码**:
- `201`: 没有信息
- `101`: APPKEY为空或不存在
- `102`: APPKEY已过期
- `104`: 请求超过次数限制

---

### 3. 六派数据 - 黄金价格API

**官网**: https://www.6api.net/api/gold/

**简介**: 提供上海黄金交易所实时/历史数据、国际金价、银行纸黄金报价等。

**价格方案**:
| 套餐 | 价格 | 调用次数 |
|------|------|----------|
| 免费测试 | 免费 | 5次 |
| 10000次 | ¥98 | 10000次 |
| 50000次 | ¥458 | 50000次 |
| 包年 | ¥16800 | 不限次 |

**核心接口**:

#### 3.1 上海黄金交易所实时金价
```
GET http://open.liupai.net/gold/shgold?appkey=您的appkey&goldid=1051
```

**goldid 参数对照**:
| goldid | 品种名称 |
|--------|----------|
| 1051 | 黄金T+D |
| 1052 | 白银T+D |
| 1053 | 黄金9999 |
| 1054 | 黄金9995 |
| 1055 | 白银9999 |
| 1056 | 铂金9995 |

#### 3.2 上海黄金交易所历史金价
```
GET http://open.liupai.net/gold/shgold_history?appkey=您的appkey&goldid=1051&date=20260206
```

**请求示例 (Python)**:
```python
import requests

url = "http://open.liupai.net/gold/shgold"
params = {
    "appkey": "您的appkey",
    "goldid": "1051"  # 黄金T+D
}

response = requests.get(url, params=params)
data = response.json()
print(data)
```

---

## 三、直接数据源

### 1. 上海黄金交易所官网

**官网**: https://www.sge.com.cn/

**数据页面**: https://www.sge.com.cn/sjzx/mrhq

**说明**: 上海黄金交易所官方网站提供每日行情数据，可通过爬虫获取。AKShare 库已封装了该数据源的接口。

---

### 2. 新浪财经

**黄金T+D行情页**: https://finance.sina.com.cn/futuremarket/goldtd.html

**说明**: 新浪财经提供实时行情展示，但未提供官方API接口。

---

### 3. 东方财富网

**黄金T+D行情页**: http://quote.eastmoney.com/globalfuture/AUTD.html

**说明**: 东方财富提供实时行情数据，可通过其网页接口获取数据。

---

## 四、接口选择建议

| 使用场景 | 推荐接口 | 理由 |
|----------|----------|------|
| 个人学习/研究 | AKShare | 完全免费，数据权威 |
| 量化回测 | AKShare | 提供完整历史数据 |
| 小型项目 | 极速数据/聚合数据 | 有免费额度，接口稳定 |
| 商业项目 | 六派数据/聚合数据 | 数据稳定，支持高并发 |
| 实时行情展示 | 商业API | 更新及时，服务保障 |

---

## 五、注意事项

1. **数据延迟**: 免费接口通常有15-30分钟延迟，实时数据需要付费接口
2. **调用限制**: 注意各接口的调用频率限制，避免被封禁
3. **数据准确性**: 以上海黄金交易所官方数据为准
4. **交易时间**: 黄金T+D交易时间为周一至周五 9:00-11:30, 13:30-15:30, 21:00-次日02:30
5. **合规使用**: 商业用途请确保已获得数据使用授权

---

## 六、相关资源

- 上海黄金交易所官网: https://www.sge.com.cn/
- AKShare 文档: https://akshare.akfamily.xyz/
- Tushare 文档: https://tushare.pro/document/2
- 金投网黄金T+D: https://www.cngold.org/gold_td/

---

*文档更新时间: 2026-02-06*
