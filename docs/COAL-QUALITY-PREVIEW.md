# 煤质到能效的情景预览（PP-050 首个单元）

`POST /api/integration/coal-quality-preview` 使用已有用户 Bearer 认证，允许管理员、运行员、能效工程师；不是旧共享密钥缓存接口。输入一个来源实例的化验、显式批次关联和工况，返回 `scenario_preview`、换算热值、血缘、既有能效引擎的计算指标。不会创建快照、触发告警或向其他系统发送事件。

请求分为四部分：

- `contract_version`: `coal-quality-energy/v1`。
- `measurement`: `source_system=coal-quality-monitor`、`source_instance`、`batch_id`、`test_id`、`metric=Qnet`、`basis=ar`、`unit=kcal/kg`或`kJ/kg`、正数`value`、带时区`measured_at`。
- `allocation`: 同一`source_instance`和`batch_id`、本地已存在的唯一`unit_code`、带时区`valid_from`和`valid_to`。这是调用者对本次情景的显式选择，不是系统推断的实际消耗关系。
- `conditions`: 原工况字段，移除`unit_id`与`coal_lhv`，要求带时区`ts`；机组由code查找，热值由化验适配。原始热值不能覆盖适配结果。

例如热值4000 kcal/kg按煤质模块既定常数4.1868转换为16747.2 kJ/kg，不使用4.184。低位/高位、收到/干燥基不可互换。来源ID必须是非空字符串，本地相同数字ID不构成跨库同一对象。显示名不参与关联。

工况必须落在关联窗口`[valid_from, valid_to)`，化验不得晚于工况。输出保留带原偏移时间及归一UTC时间、测量年龄；没有足够业务依据设统一过期阈值，调用方必须评估化验代表性。没有时区的旧记录需先查明来源时区，不能直接补Z。未实现源端导出/拉取，调用方需从经过核对的源记录构造契约；请求中的身份声明不是外部真实性证明。

API拒绝未知字段、非有限数值及基本物理范围错误。用于情景预览的限制包括负荷1–2000 MW且不超过机组容量、厂用电小于负荷、煤流量(0,10000] t/h、热值(0,10000] kcal/kg等价值。计算模型沿用已有机组设计参数；返回有限数值不代表工况经过现场校准。

本单元不证明入厂煤已经入炉，不自动消费旧无血缘缓存，不持久化映射与结果，不替代配煤/煤场消耗分配。下一步是来源导出契约与持久关联、实际批次消耗证据以及执行反馈；PP-050总体仍进行中。

验证入口：`cd backend && python -m pytest tests/test_coal_quality_preview.py -q`。测试以合成数据比较预览和真实快照计算结果，核查预览无写入、单位等价、身份错配、基准/时间/角色/数值拒绝。
