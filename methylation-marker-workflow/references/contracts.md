# 输入、模型及适配契约

## task.json

schema_version=1；task_id 唯一；task_type 为 tissue_source/tumor_normal/low_fraction_cfdna/multicancer_source；protocol 为 fixed_panel/discovery。task_definition 声明正负标签和合法解释；external_label_use=evaluation_only。budget 包括运行秒数、内存、CPU/GPU、允许读取样本/区域数；未知预算不能启动运行。seed 保留原协议。statistical_semantics 明确当前入口的统计对象，不提供通用 alpha 默认值。

artifacts 为 path/sha256 清单（小文件路径相对实验目录，或绝对路径）；包括角色表、面板、CpG 字典/转换审计、实现/导入代码、配置、阈值、权重、历史预测。阶段推进前核对哈希；远端尚未可读不能用虚构本地文件冒充。v1 工具只检查列出的本地文件，不验证远端文件和整个依赖闭包，执行者须逐项登记代码依赖。

## samples.csv

一行一个样本，sample_id 不重复。donor_id 和 donor_evidence 必须有来源；缺失则可做元信息整理，但不能通过分组验收。cohort_id 是来源队列，不用于把同一供体跨队列伪装成不同人。donor_id 使用全局身份；同一供体不能跨 train/calibration/test 或 fold；背景同 label 在一个训练侧 fold 中。audit 仅 audit split；external 仅 test split。器官特定历史 audit 选择的例外必须披露，不能套用纯 audit 宣称。

format=pat/beta/summary/mhap/patterns/features；build=hg19/hg38（其他版本需扩展契约）；coordinate_system= cpg_ordinal_1based / base_pair_declared / region_id。PAT/beta 用 CpG ordinal；mHap 用声明的碱基端点。summary 含两类坐标时核对各字段。patterns/features 以 region_id 链接冻结面板。PAT/mHap index_path 不为空。此表的快速检查不读大文件内部；阶段 1 另保存文件存在性、索引、端点、CpG 字典和实际格式检查。

## model-card.json 和 registry.json

所有 builtin/user 都用 assets/model-card.json；unknown 用 null，不填猜测值。registry 引用本地卡文件和 SHA-256。模型状态链为 registered/metadata_checked/smoke_passed/interface_passed/evaluable/frozen；失败分支信息见 SKILL.md。状态提高时需写入小试及接口审计文件，阶段 2 的证据引用卡/注册表和这些审计。tool 的 check 仅强制可参与评测/冻结模型信息完整；登记状态允许待补，但阶段 2 接受必须所有启用模型 evaluable/frozen。

input_contract 声明缺失语义、count_weighted（不能 unknown）、格式、build、k、mask、覆盖门槛及张量轴；unsupported 是明确不兼容，不自动补0。output_contract 声明 output_type/meaning/direction/log_base/numerator/denominator/smoothing/coverage_condition/pooling。非 logLR 字段可为 not_applicable。source_fraction/evidence_coefficient/probability/score/loglr 分开。训练卡记录拟合、选择、校准各数据边界和预训练重叠。

entrypoint 是 argv 列表，仅用于审阅和生成执行方案，checkpoint 不运行。environment 包括依赖锁/版本及 CPU/GPU；resources 为限额；smoke 为输入、预期结果、容差、日志/QC路径。容器镜像使用固定摘要，不用 latest；v1 没有容器执行器。

## 统一适配结果（人工映射，保留原始文件）

筛选表：region_id/chrom/start_bp/end_bp/start_cpg/end_cpg/k/genome_build/coordinate_system/rank/metric/metric_definition/decision/reason。片段表：sample_id/region_id/pattern/observed_mask/count/raw_evidence/output_type/scorable/reason。样本长表：sample_id/donor_id/cohort_id/task_label/model_id/model_version/panel_version/raw_score/output_type/calibrated_output/calibration_version/coverage/rejected/reason/status；不可评分留行，raw_score=null。

不改原表，新增映射表和映射说明。样本/模型/面板组合唯一，输出覆盖应与输入样本清单一致；漏行记失败。合法概率需校准数据边界和适用范围，ECDF percentile 不是疾病概率。保存阈值来源、严格大于/大于等于规则、PR-AUC 实现定义；core 的 pr_auc 是排序 average-precision 风格，不能悄悄改成梯形积分。

模型状态演进在 init 前按版本保存；init 后注册表不可修改，新状态或新增模型进入新实验。registry 是人工维护的注册快照，v1 不自动执行模型接入状态迁移。
