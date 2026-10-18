# DSH 同花顺模拟持仓与回测回放

在 DeepSeek Harness（DSH）左侧快捷栏增加「模拟持仓」和「回测回放」两个入口，展示：

- 同花顺模拟账户总资产、可用资金、持仓市值、持仓浮盈
- 持仓列表：名称/代码、持仓/可用、成本/现价、市值、浮盈
- 分钟 K 线：1/5/15/30/60 分钟，MA5/MA10、MACD、成交量
- 日线：MA5/MA10、MACD
- 资金流：今日主力/超大单/大单/中单/小单，近 5 日主力与超大单
- 五档盘口：买卖五档价格、挂单量、价差
- 回测回放：选择本地回测、日期区间和回放日期，查看权益曲线、回放持仓、逐笔交易和个股历史日线 K 线

## 架构

```text
DSH 左侧栏入口 + 主面板（lib/client.js）
        |
        |  /ths-dashboard/api  （同源代理）
        v
宿主插件（lib/index.js）
        |
        |  启动并转发到 127.0.0.1:8766
        v
ths_sim.dashboard_server  （Python 后端，源码已随包放在 python/ths_sim）
        |
        +-- 同花顺模拟盘：账户 / 持仓 / 五档盘口
        +-- 新浪：分钟/日线 K 线，资金流
        +-- 腾讯：盘口与名称兜底
```
宿主插件会自动启动包内自带的 Python 服务；DSH 关闭时停止它。若服务没有启动，面板错误区会提示，也可以手动运行：

```powershell
cd <package-root>
$env:PYTHONPATH = "$PWD\python"
python -m ths_sim.dashboard_server --port 8766
```

## 安装

从 npm 安装：

```powershell
dsh plugin --profile desktop add dsh-ths-dashboard
```

本地开发时用 `link:` 安装当前目录：

```powershell
dsh plugin --profile desktop add "link:<this-directory>"
```

新增客户端 bundle 后需要重启 DSH 桌面客户端，左侧栏才会出现「模拟持仓」。

## 数据口径与限制

- 账户、持仓、五档盘口来自同花顺模拟炒股网页接口
- K 线与新浪资金流来自公开网页接口
- 资金流中的主力/超大单是公开数据口径，不是逐笔十档 L2
- 回测目录通过用户目录 `.ths_sim/dashboard.json` 的 `backtest_root` 配置，或环境变量 `THS_BACKTEST_ROOT`：

```json
{"backtest_root": "C:\\path\\to\\local_backtest\\out"}
```
- 回测回放不提供历史分钟 K、逐笔盘口或 L2；这些数据无法从历史存档复原
- 当前只读展示，不下单；交易仍通过 ths_sim CLI 或后续策略执行器
- Cookie 和账户号不会发送到浏览器面板，也不会出现在前端 JSON 中

## 文件

```text
lib/index.js       宿主：启动 Python 服务 + 同源 API 代理
lib/client.js      浏览器：模拟持仓/回测回放入口、持仓表、K线/MACD、资金流、五档盘口
cordis.patch.yml   DSH bundle patch
package.json       DSH 插件描述
```
