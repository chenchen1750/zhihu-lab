# 问题登记字段规范

一个知乎问题一个 Markdown 文件：YAML frontmatter（英文键、中文值）+ 固定小节。
`python3 tools/zhihuctl.py validate` 按本文件校验。

## 字段

| 字段 | 取值 | 说明 |
|---|---|---|
| `id` | `Q-0001` | 四位序号，全库唯一，与文件名前缀一致，永不复用 |
| `kind` | `question` | 固定 |
| `title` | 知乎问题原标题 | 照抄，不要改写 |
| `url` | `https://www.zhihu.com/question/<数字>` | 只收问题页，不收专栏 `zhuanlan` |
| `series` | `S-01`～`S-05` 或 `null` | 所属系列，见 `plan/` |
| `status` | `inbox` / `active` / `answered` / `dropped` | 必须与所在目录一致 |
| `priority` | `P0` / `P1` / `P2` | P0 = 本季度一定写 |
| `followers` | 整数或 `null` | 关注数。知乎反爬，**人工填** |
| `answers_count` | 整数或 `null` | 回答数。人工填 |
| `checked` | `YYYY-MM-DD` 或 `null` | 上次人工核对热度的日期 |
| `matched_entries` | 列表，如 `[R-0137, R-0047]` | km-harness 条目 id。**定期检查的核心字段** |
| `angle` | 一句话 | 你的回答角度，与大众答案的区别 |
| `answer_id` | `A-0001` 或 `null` | 已写的回答编号 |
| `published_url` | URL 或 `null` | 发布后回填 |
| `created` / `updated` | `YYYY-MM-DD` | |

## 正文小节

固定五节，缺节 validate 会报：

- `## 为什么适合` —— 为什么这题轮得到你答，别人答不出什么
- `## 回答角度` —— 主论点 + 分论点骨架
- `## 可用条目` —— 逐条列 `matched_entries`，每条一句说明怎么用
- `## 竞品观察` —— 现有高赞答案在讲什么，缺什么；专栏链接放这里
- `## 备注` —— 其他

## 状态流转

```
inbox ──评审通过──> active ──发布后──> answered
  └────────评审否决 / 过时────────> dropped
```

用 `zhihuctl.py promote <id>` 和 `drop <id> --reason "…"` 流转，不要手工挪文件。
