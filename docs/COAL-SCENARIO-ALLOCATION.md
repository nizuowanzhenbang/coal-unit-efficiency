# 煤批次与机组的情景关联

本功能保存由操作员明确声明的情景关系，供预览时按ID选择：煤质来源实例、批次ID、机组code、带时区的起止时间和关联依据。左闭右开时间窗口在保存时转为UTC，原始操作员、请求UUID与创建时间保留。记录不可通过本接口修改或删除。

`POST /api/integration/coal-quality-allocations` 需要运行员、能效工程师或管理员；请求包含 `request_id`（UUID）、`source_instance`、`batch_id`、`unit_code`、`valid_from`、`valid_to`、`evidence`。同一操作员用同UUID、相同内容重放返回原记录；内容或操作者不一致返回409。通过 `GET /api/integration/coal-quality-allocations/{id}` 查询，登录用户可读。丢失ID时，可使用 `GET /api/integration/coal-quality-allocations?source_instance=...&batch_id=...` 按完整来源身份查询；最多返回最新100条，`truncated=true` 表示还有更多记录。

`POST /api/integration/coal-quality-preview/saved` 使用 `allocation_id`、煤质导出的 `measurement` 与能效 `conditions`，按保存的关联执行已有情景预览；若来源实例、批次或时间窗口不匹配则拒绝。预览返回关联ID，但不写运行工况、效率记录或告警。操作者仍需保存煤质导出的 `time_provenance`：该声明当前不作为预览输入或由本关联记录保存。

允许不同关联时间窗口重叠，支持同批煤可能用于多个机组的情况；系统不自动选择、合并或判断哪条声明真实，操作员必须核对后明确选择ID。关联说明、单位、来源标识和人工时区依据不是实测入炉证据，不能用作现场消耗核算。自动建立批次消耗关系、匹配已有运行快照和持续效果验证均待后续设计。

升级增加 `coal_scenario_allocations` 新表；沿用启动 `create_all` 创建新表，不迁移既有表或修改原工况数据。部署需按实际数据库权限、备份及发布流程进行；本轮以独立SQLite及PostgreSQL实例运行关联和同UUID并发回归；未执行现场升级或负载性能测试。
