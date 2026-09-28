# zhihu-lab 项目约定

知乎职场内容库：把 `km-harness/knowledge/` 的知识条目，匹配到具体的知乎问题上，产出回答。沟通用中文。

定位见 `plan/POSITIONING.md`，系列规划见 `plan/S-*.md`。

## 目录

- `plan/`：定位与五个系列的规划。手工维护。
- `questions/`：知乎问题登记，一题一文件。规范见 `questions/SCHEMA.md`，选题标准见 `questions/REVIEW.md`。
  - `inbox/` 待评估 → `active/` 已选定要写 → `answered/` 已发布；`dropped/` 已放弃。
- `answers/草稿/`、`answers/已发布/`：回答草稿与已发布稿。模板 `answers/TEMPLATE.md`。
- `state/scan.json`：定期检查的状态快照，由脚本读写，不要手改。
- `tools/zhihuctl.py`：管理脚本（new / validate / index / promote / drop / lint / scan / show），依赖 PyYAML。
- `runbook/定期选题检查.md`：每周固定跑的流程。

## 上游依赖

知识条目来自 `../km-harness/knowledge/`，本库**只读**它，不修改。
问题文件里的 `matched_entries` 填的是那边的条目 id（如 `R-0137`）。

## 规则

- 新问题一律用 `python3 tools/zhihuctl.py new …` 生成到 `questions/inbox/`，不要手工起编号。id 永不复用。
- `questions/INDEX.md` 由脚本生成，不要手改。手工改过问题文件后运行：
  `python3 tools/zhihuctl.py validate && python3 tools/zhihuctl.py index`
- 只有 `status: active` 的问题才开始写回答。进 active 要先过 `questions/REVIEW.md` 的选题清单。
- 知乎反爬，`followers` / `answers_count` 脚本抓不到，由人在 App 里看了手工填，并更新 `checked` 日期。
- 只登记 `www.zhihu.com/question/...`。`zhuanlan.zhihu.com/p/...` 是专栏文章不能回答，要留就放进问题文件的「竞品观察」。

## 脱敏红线（写任何对外内容前必查）

以下一律不得出现在 `answers/` 里：

- 集群规模、机器数量、成本绝对值、Pod 数量等内部经营数据 —— 只能用比例和倍数
- 内部看板、飞书文档、内网域名的任何链接
- 公司名、部门名、同事姓名或花名、领导职位指代到可识别的程度
- 任何 token、密钥、webhook 地址、账号
- 未脱敏的线上故障细节

拿不准就删。发布前对着这一节过一遍。

## 人称与口吻（对外内容一律遵守）

**不用第一人称叙事。** `answers/` 里不出现作为叙述者的「我」。

默认写法是**第二人称场景 + 观察者视角**：

- **讲处境用「你」**，把读者直接放进场景里，开头尤其如此。
  例：「你指出了一个方案的根本问题，方案被推翻了。新方案是你写的。然后，推进这件事的人不是你。」
- **讲方法用观察者口吻**：「见过不少人卡在这一步」「真正破局的人做的是另外三件事」「常见的做法是」。

三条例外，「我」可以出现：

1. 引述读者的内心话 —— 「大概率在反复想同一句话：**我明明是对的啊**」
2. 引述对话中他人的原话 —— 「这东西得攥在我们自己手里」
3. 引用 `km-harness` 条目的原文摘录时保留原始表述

**不要用「我有一个朋友」。** 这个说法在知乎基本等同于"就是我"，达不到隐去自己的目的，
反而更像刻意遮掩。也不要把自己的经历安到一个具名的虚构人物身上。

要具名第三人称案例（如「老周」）时单独说，不作为默认。

自查（同时查脱敏红线、条目引用、字数）：

```bash
python3 tools/zhihuctl.py lint            # 检查 answers/ 下所有稿件
python3 tools/zhihuctl.py lint --fix      # 顺便同步 frontmatter 的 word_count
```

人称命中的每一处，确认属于上面三条例外之一，否则改写。
脱敏命中的一律必须处理，`lint` 会以非零码退出。

## 工作方式

- 大任务先给计划，用选择题逐项确认，有 95% 以上把握再动手。
- 不主动 `git commit`，由用户自己检查后提交。
- 文件和目录命名用「编号-中文标题」。
