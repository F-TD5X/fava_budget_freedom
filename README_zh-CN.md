# Fava Budget Freedom

[English](README.md) | 简体中文

Fava Budget Freedom 是一个 [Fava](https://beancount.github.io/fava/) 的扩展插件，旨在提供更灵活、强大的预算管理和可视化功能。它支持基于通配符的账户匹配、多种预算周期以及预算滚存（Rollover）机制，帮助你更好地实现财务自由。

## 主要特性

- **灵活的预算定义**：使用自定义指令定义预算，支持通配符（如 `Expenses:Food:*`）。
- **多种周期支持**：支持 `monthly`（月度）、`weekly`（周度）、`quarterly`（季度）和 `yearly`（年度）预算。
- **预算滚存 (Rollover)**：支持月度预算的滚存功能，上月未用完的额度自动累积到下月，超支则扣减下月额度。
- **折旧分摊支持**：智能处理 `beancount_periodic.amortize` 插件生成的分摊交易，一次性支出计入预算，分摊交易自动忽略，并以子项目形式展示折旧明细。
- **可视化进度条**：直观展示预算使用进度，并根据时间进度显示理想参考线（仅限整年视图）。
- **智能时间范围**：支持 Fava 的时间筛选，默认显示今年至今（YTD）的预算执行情况。
- **交互式报表**：点击账户模式可直接跳转到对应的账户详情页面。

## 使用方法

### 1. 安装插件

你可以通过 pip 直接从 GitHub 安装：

```bash
pip install git+https://github.com/Leon2xiaowu/fava_budget_freedom.git
```

或者，如果你下载了源码，也可以在源码目录安装：

```bash
pip install .
```

确保安装后 `fava_budget_freedom` 在你的 Python 环境中可用。

### 2. 配置 Beancount

在你的 `.beancount` 文件中加载插件：

```beancount
2025-01-01 custom "fava-extension" "fava_budget_freedom"
```

### 3. 定义预算

使用 `custom "budget"` 指令定义预算。

**语法：**

```beancount
YYYY-MM-DD custom "budget" "AccountPattern" "Period" "Amount Currency" ["rollover"]
```

- **AccountPattern**: 账户名称或通配符模式（例如 `Expenses:Food` 或 `Expenses:Food:*`）。
- **Period**: 预算周期，可选值：`monthly`, `weekly`, `quarterly`, `yearly`。
- **Amount Currency**: 预算金额和货币（例如 `2000 CNY`）。
- **rollover**: (可选) 仅适用于 `monthly`，开启后支持预算累积。

**示例：**

```beancount
; 每月餐饮预算 2000 USD，开启滚存
2025-01-01 custom "budget" "Expenses:Food:*" "monthly" "2000 USD" "rollover"

; 每周书籍预算 20 EUR
2025-01-01 custom "budget" "Expenses:Books" "weekly" "20.00 EUR"

; 年度旅行预算 2500 EUR
2025-01-01 custom "budget" "Expenses:Holiday" "yearly" "2500.00 EUR"
```

### 4. 折旧分摊支持

插件支持与 `beancount_periodic.amortize` 插件配合使用，智能处理折旧分摊交易。

**工作原理：**

1. **一次性支出计入预算**：使用 `Equity:Amortization:*` 账户的一次性大额支出会被自动转换为对应的 `Expenses:*` 账户并计入预算
2. **自动忽略分摊交易**：由 `amortize` 插件自动生成的每月分摊交易不会重复计入预算
3. **明细可视化**：在预算报表中，折旧分摊项目会作为子项显示在对应的支出类别下

**示例：**

```beancount
; 配置 amortize 插件
plugin "beancount_periodic.amortize" "{'generate_until':'today'}"

; 定义房租预算
2025-01-01 custom "budget" "Expenses:Home:Rent" "yearly" "12000 USD"

; 一次性支付年度房租，分摊到12个月
2025-10-03 * "Landlord" "Annual Rent Payment"
  Liabilities:CreditCard:0001     -12000 USD
  Equity:Amortization:Home:Rent
    amortize: "1 Year /Monthly"
```

**预算统计效果：**

- `Expenses:Home:Rent` 预算会统计到完整的 12000 USD 一次性支出
- 每月自动生成的 1000 USD 分摊交易（`Equity:Amortization:Home:Rent` → `Expenses:Home:Rent`）会被自动忽略
- 在报表中，`Expenses:Home:Rent` 行下方会显示一个子项 `↳ Equity:Amortization:Home:Rent`，展示折旧金额

**注意事项：**

- 折旧分摊的判断规则：如果交易中存在 `Equity:Amortization:*` 开头的收入账户（负数金额），则该交易被识别为分摊生成的交易并跳过
- 一次性支出交易中，`Equity:Amortization:*` 的支出（正数金额）会被转换为 `Expenses:*` 进行预算匹配
- 点击子项中的 `Equity:Amortization:*` 账户名称可以查看该账户的详细交易记录

## 开发与启动

### 环境准备

建议使用 Python 虚拟环境进行开发，以避免污染系统环境。

1.  **创建虚拟环境**

    ```bash
    python3 -m venv venv
    ```

2.  **激活虚拟环境**

    - macOS / Linux:
      ```bash
      source venv/bin/activate
      ```
    - Windows:
      ```bash
      venv\Scripts\activate
      ```

3.  **安装依赖**

    ```bash
    pip install fava beancount
    ```

### 启动项目

在本地开发环境中，可以使用提供的示例文件进行测试。

1.  设置 `PYTHONPATH` 为当前目录，以便 Fava 能加载插件。
2.  启动 Fava。

```bash
# 设置 PYTHONPATH 并启动 Fava
export PYTHONPATH=$PWD
fava example.beancount
```

或者直接运行：

```bash
PYTHONPATH=. fava example.beancount
```

访问 `http://localhost:5000` 并在侧边栏中找到 "Budget Freedom" 扩展页面。
