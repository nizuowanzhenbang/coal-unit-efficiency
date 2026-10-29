# 煤质时间依据与情景预览

PP057：时间声明由操作者提交，不证明真实化验、自动采集或实际入炉。

1. 煤质系统的 energy-measurement 导出包含 measurement 和 time_provenance。
2. 用 OPERATOR / ENERGY_ENG（或管理员）身份向 `POST /api/integration/coal-quality-measurements` 提交 request_id（新UUID）、measurement、time_provenance。响应包含 id、提交人、提交时间、内容 SHA256。保留该 id。
3. 用登录身份 `GET /api/integration/coal-quality-measurements/{id}` 查回；普通查看者可以读取但不能创建。权限沿用本系统角色规则，不提供多租户隔离。
4. 使用已有批次—机组情景关联 id，向 `POST /api/integration/coal-quality-preview/evidenced` 提交 measurement_id、allocation_id、conditions。返回完整 measurement_evidence 和计算结果。系统检查来源实例、批次及时间窗口，不写运行快照。

时间依据格式与煤质导出一致：kind 必须 caller_declared_offset，offset_minutes 为 -840 至 840 整数，stored_time 为原始无时区钟面时间，evidence 为 1–500 字非空说明。偏移必须与 measurement.measured_at 的原始偏移一致，钟面时间必须与 stored_time 一致；等时但换了偏移也拒绝。UTC 可表示性沿用测量契约。

记录不可通过 API 修改或删除。同一UUID、同一提交人、相同规范内容重放返回200；首次201，内容或提交人冲突409。修正必须新UUID，保留旧id。不同UUID允许相同测量，不提供自动选最新版；调用方需保存返回id。SHA256覆盖契约版本、完整规范测量和时间声明，表示本次接收内容的版本，不是上游修订号、签名或真实性认证。JSON键顺序不影响摘要，说明文本/原始时间拼写改变会产生不同内容版本。

旧的 request 内预览和 saved 关联预览保留；它们不具有本功能的持久时间证据，不能因此标为已存证。

升级：正常应用启动的 init_db/create_all 新增独立 coal_measurement_evidence 表，不改写旧表、不补造旧依据；部署前备份并在隔离环境验证升级。回滚旧代码不删除该表。当前自动测试覆盖隔离建表及SQLite/PostgreSQL行为，不证明现场升级、生产负载、数据库被人工篡改后的恢复。
