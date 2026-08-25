# Burn Before Reset 🔥

[English](./README.md) · 中文

> 本页是中文说明页（不是逐句对译）：讲清是什么、怎么跑、边界在哪。完整文档、安全模型细节与最新状态以英文 [README](./README.md) 为准。

**别烧 token，烧掉你的积压。**

订阅额度每周重置，没用完就作废。Burn Before Reset 把这些即将过期的额度，变成**可复核的真实成果**：agent 自己从你允许的来源（会话日志 / 代码仓库 / 文档目录）里找活干，骑着内层额度窗口（用完就睡、补充了再干），只在你给定的外层重置时间前**机械硬停**。醒来收一份 Morning Report。

Token 消耗是约束，不是 KPI——每个任务都追溯到真实来源里的真实信号，绝不为烧而烧。

## 现状（诚实声明）

**公开候选（candidate）。尚未证明可无人值守用于敏感数据。**默认路径是 plan-only（只出计划不执行）；`--execute` 请先在自己的源上盯着跑过再谈信任。完整闸门台账见 [VALIDATION.md](VALIDATION.md)。

## 快速上手

需要 Python 3.11+、Git，以及本地已登录的 Codex CLI 或 Claude Code CLI。

```bash
cp examples/config.example.toml config.local.toml
# 先编辑 config.local.toml：把占位路径换成你真实的来源目录，
# output_root 指向一个持久位置
python3 scripts/bbr.py validate-config --config config.local.toml
python3 scripts/bbr.py plan --config config.local.toml
```

`validate-config` 对占位路径会以 exit `2` 拒绝——那是闸门在工作，不是 bug。执行（`run --execute`）是双重门控的，细节见英文 README 的 Quick start 与 Safety model。

## 安全要点（速览）

- 你提供带时区的绝对重置时间；默认在重置前 15 分钟硬停，低于 10 分钟直接拒绝。
- 计费 fail-closed：Credits 余额未知、Auto top-up 状态未知、环境里有 API key、或出现计费 / 限流错误，一律停。
- 只读索引显式允许的来源；绝不改动源目录，绝不 push / 删除 / 对外发送 / 花钱。
- 队列冻结后不再追加；找不到真活就诚实结束，不编造任务。

## 不做什么

- 不从未公开接口抓取额度 / 重置数据；不保证服务端计费行为。
- 不用 API key、付费 Credits、供应商 fallback 或云端任务。
- 不改你的笔记库和代码仓库；不开 PR、不建远端、不 push。

## 许可

MIT — 见 [LICENSE](LICENSE)。
