# Xinsight

> 心识 — 关于心灵与关系的个人操作系统

## 这是什么

心识（Xinsight）是一个借助 AI 对话来经营内心世界的个人系统。

通过维护结构化的信息文件和 AI 规则，让每一次对话都建立在对自己、对他人的深度理解之上。

## 项目结构

```
xinsight/
├── workbench.md           # 工作台：AI 与用户的动态交互面板
│
├── self/                  # 自我认识（按需扩展）
├── crush/                 # Crush
│   └── her.md             # 基本信息、性格特质、关系阶段
├── growth/                # 自我成长（按需扩展）
│
├── tools/                 # 工具
│   └── wx_chat.py         # 微信聊天记录查询
│
└── .cursor/rules/         # AI 规则
    ├── xinsight.mdc       # 核心规则
    ├── message-workflow.mdc  # 消息应对工作流
    └── wechat-access.mdc  # 微信消息访问指南
```

## 消息应对工作流

收到消息后的标准流程（详见 `message-workflow.mdc`）：

1. **AI 获取上下文** — 同步微信最新消息 + 读取人物档案
2. **AI 写入工作台** — 意图分析、策略方向写入 `workbench.md`，具体回复方案折叠隐藏
3. **你先独立回复** — 打开 `workbench.md` 预览，看分析但不展开参考答案，写出自己的回复
4. **展开对比 + 成长反馈** — AI 将对比分析和心理洞察追加到 `workbench.md`

## 如何使用

1. **填充信息** — 逐步完善 `.md` 文件，从基本信息开始，慢慢积累
2. **对话成长** — 在 Cursor 中开启对话，AI 基于你维护的信息和实时聊天记录给出建议
3. **持续迭代** — 每次新的认知和变化，更新到对应文件中

## 微信消息集成

通过 `tools/wx_chat.py` 可以直接读取本地微信聊天记录，让 AI 基于真实对话内容进行分析和建议。

**前提**：微信 PC 端正在运行 | 已安装依赖 `pip install pywxdump`

```bash
python tools/wx_chat.py sync               # 同步最新数据
python tools/wx_chat.py contacts            # 列出最近联系人
python tools/wx_chat.py chat <昵称或备注>    # 查看某人聊天记录
python tools/wx_chat.py search <关键词>      # 搜索聊天内容
python tools/wx_chat.py rebuild             # 重建数据库（清理膨胀）
```

> 详细说明见 `.cursor/rules/wechat-access.mdc`

## 理念

- **你才是专家** — AI 是镜子和工具，不是权威。所有决策由你做出
- **诚实是基石** — 对自己越诚实，系统越有效
- **成长是过程** — 没有标准答案，只有持续的自我探索
