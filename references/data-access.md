# 数据获取与证据层级

本文件在需要选择比赛、获取数据、判断解析状态或处理接口失败时读取。

## 输入配置

从当前项目记忆读取：

- `account_id`
- `api_base`
- `preferred_entry`：`auto`、`page-first` 或 `json-first`
- `replay_parse_managed_by_server`

本项目常用接口由 `api_base` 拼接：

- 最近比赛 JSON：`/matches?page=1&page_size=20`
- 最近比赛页面：`/page/recent`
- 单场完整 JSON：`/match/{match_id}`
- 单场可见文本页面：`/page/match/{match_id}`

不要要求用户把已经给出的 Match ID 再包装成 URL。

## 确定 Match ID

- “复盘开始 + Match ID”：直接使用该 ID
- “最近一把”：取最近列表第一场
- “第 N 把”：取最近列表第 N 场
- 只有“复盘开始”：列出最近比赛供选择，显示序号、Match ID、英雄、胜负、KDA、时长、解析状态
- 已在同一场复盘上下文中：沿用当前 Match ID

最近列表只负责选比赛和初步状态，不足以完成专业复盘。

## 入口选择

- 配置为 `auto`：Chat/浏览器环境先用页面入口；能稳定读取 JSON 的工具环境先用 JSON 接口
- 配置为 `page-first`：先访问 `/page/match/{match_id}`，再尝试 JSON 接口
- 配置为 `json-first`：先访问 `/match/{match_id}`，再尝试页面入口
- 任一入口拿到完整数据后停止重复请求

若完整接口失败，依次尝试另一入口、用户上传的完整 OpenDota JSON、用户提供的其他完整比赛数据。

## Match ID 范围

若服务端返回404并说明比赛不在保存范围：

- 告知用户该 Match ID 当前不在服务器保存范围
- 不枚举或猜测其他 Match ID
- 不根据 ID 猜比赛内容

## Replay Parse 与状态冲突

若项目配置表明解析由服务端托管，Agent 不得向 OpenDota `/request/{match_id}` 发送 POST。

`parsed`、`has_parsed` 和 `parse_status` 只是状态标签，不能单独证明数据完整。是否允许完整复盘，只由实际关键字段决定。

状态处理：

- `parsed=true` 但 version、teamfights、objectives 或经济/经验曲线缺失/为空：判定为缓存状态不一致，不能按完整解析处理
- `has_parsed=false` 但全部关键字段实际存在：记录状态冲突，按实际字段判定完整度
- 标签与字段冲突时，必须在数据限制中报告“自建缓存状态不一致”
- `requested` / `waiting`：服务端已申请，不能重复；可重新查看比赛页面确认状态
- 尚未申请：访问项目配置的比赛页面，让服务端决定是否自动申请
- `unavailable`：再次检查当前完整接口；仍缺字段时只能做有限分析

如果 Match ID 已被自建服务确认在允许范围内，但自建单场缓存字段不完整或明显落后，可以只读回退到：

`GET https://api.opendota.com/api/matches/{match_id}`

- OpenDota GET 返回完整关键字段时，可用该响应完成复盘，并明确说明自建缓存滞后
- OpenDota GET 仍不完整时，按部分解析处理
- 此回退只允许 GET；仍不得向 OpenDota `/request/{match_id}` POST
- 自建服务已经对 Match ID 返回范围外404时，不使用回退绕过该限制

解析中时可以基于摘要给有限判断，但必须明确写明：

`当前仅为摘要数据分析，不等同于完整 Replay 复盘。`

## 完整性检查

完整复盘必须检查，且以下字段均实际存在并非空：

- `players`
- `objectives`
- `teamfights`
- `radiant_gold_adv`
- `radiant_xp_adv`
- `version`

上述任一字段缺失或为空，一律不能判定为完整解析。状态标签即使写着 `parsed=true` 也不能覆盖此规则。

同时确认比赛开始时间、持续时间、胜方和补丁标识。历史比赛应按该场补丁理解英雄、技能和装备，不能把当前版本机制直接套入旧比赛。

按任务继续检查：

- 玩家曲线：`gold_t`、`xp_t`、`lh_t`、`hero_damage_t`
- 对线与位置：`lane`、`lane_role`、`lane_pos`、击杀日志
- 装备：`purchase_log`、`purchase_time`、`item_uses`
- 技能：`ability_uses`、`ability_targets`、团战窗口内技能记录
- 输出对象：`damage_targets`、`damage_inflictor`、`damage_taken`
- 目标：`objectives`、Roshan、Aegis、塔、兵营、基地
- 决策资源：`buyback_log`、买活次数、最终金钱
- 辅助：`obs_log`、`sen_log`、控制、治疗、救人和功能技能

英雄、物品和技能若只给数字 ID，应使用与数据源匹配的 constants 映射，不能凭印象猜名称。`teamfights` 是解析器识别出的战斗窗口，不保证覆盖全部战斗；必须与击杀日志、经济/经验突变和目标事件交叉核验。

部分字段缺失不等于可以编造，也不必放弃所有分析。降低对应结论强度并说明限制。

## 数据缓存与复用

同一任务内取得完整 JSON 后应复用。只有这些情况重新获取：

- 服务端解析状态可能已经从等待变为完成
- 用户切换 Match ID
- 当前副本缺少专项分析必需字段
- 数据响应被截断或校验失败

## 失败处理

所有自动入口都失败后，才请用户提供完整 JSON 或比赛文件。没有完整数据时，不得声称完成了时间轴级、位置级或技能顺序级复盘。
