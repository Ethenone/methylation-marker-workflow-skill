# 十阶段检查点

| id | 阶段 | 人工审阅的通过证据 |
|---|---|---|
| 0 | 任务与数据登记 | 目标、角色/供体证据、拆分、build、权限、预算、输入清单 |
| 1 | 已有格式/QC | 实际文件/索引、PAT ordinal/mHap 端点、CpG 字典、mask/count、QC |
| 2 | 模型登记/试跑 | 启用模型 evaluable/frozen，卡哈希、微型测试及接口结果、模型库快照 |
| 3 | 粗筛 | 已声明的方法配置、覆盖过滤、候选规模/数值、训练侧标签 |
| 4 | 二筛 | 样本与 label 均衡、方向/覆盖、留一稳定性、audit 使用边界 |
| 5 | 提取/局部模型 | 索引提取与已有 summary 对照、count、边缘化、先验、坐标、输出语义 |
| 6 | 内部比较 | 供体/label 完整折，固定面板 OOF 或嵌套范围、配对预测、成本及失败 |
| 7 | 冻结 | 面板/注册表/权重/阈值/拒判/校准哈希，选择和外部标签隔离记录 |
| 8 | 外部比较 | 权限、逐 CpG 转换、同模型校准、冻结预测后贴标签、配对患者指标 |
| 9 | 报告归档 | 样本长表/覆盖/拒判/失败、区间方法、provenance、未决选择 |

passed/reused 要 evidence.json 中 exit_code=0、checks 非空且全部 passed=true、artifacts 至少一个 path/sha256（必须包含结果、配置、日志、退出码文件和实际 SUCCESS 标志，历史名字可不同），note 说明结果与方法边界。辅助工具校验哈希，不解析所有历史输出；原成功标志与实际数值/QC须由执行者核对，不能仅凭进程消失通过。

reused 另需 reuse_audit：input_match/code_match/config_match/semantics_match 均 true，并引用匹配审计。差异存在新建任务，不能勾选 true 掩盖差异。not_applicable 只允许 fixed_panel 的 3/4；仍需不可变证据文件及原因。running/failed/blocked 需要原因；失败填实际退出码，暂未结束用 null。证据文件每次转移新建，接受后不能编辑。

工具 check 验证 task/samples/registry/model cards 和已接受证据摘要，status 展示下一阶段。未完成的第一个阶段才可 record；failed/blocked 可重新 running 或提交修复后的完成证据，历史保留。running 状态显示等待收集；不自动认为失联就是失败。完成全部十阶段后不再推进。

state.json 内保留冻结登记哈希、十阶段状态、事件列表（证据绝对路径、摘要、文件摘要、时间）。单个原子状态文件减少状态与事件不同步；锁文件拒绝并发写。输入一旦初始化后变更则 check 拒绝；换模型/配置/面板新实验。禁止直接拷贝 SUCCESS 当作本次成功；不得手改状态隐藏失败。

新增识别模型通常复用既有阶段 3–5；新注册快照需重新审阅阶段 2，内部比较及冻结/外部评测属于新版本。换筛选模型影响 3–9；换区域/参考/坐标影响提取及下游。v1 只提供显式复用审计，不做自动依赖图执行。

验收修复：状态阶段与事件历史重放必须一致；failed 需要实际非零退出码，未执行/信息不足使用 blocked。model_failures 可逐项记录 model_id/status/exit_code/reason/log；事件保存此清单与退出码，冻结 registry 不被失败重写。
