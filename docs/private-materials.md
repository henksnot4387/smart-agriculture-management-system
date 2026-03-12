# 私有资料处理说明

开源版仓库不再跟踪以下类型的文件：

- 合作方白皮书、接口说明、客户导出表
- 真实参数目录与系统 ID 对应关系
- 任何带有客户名称、账号、密钥、内部地址的文档

建议做法：

1. 私有文档放到 `docs/private/` 目录。
2. 真实参数目录放到 `backend/data/hoogendoorn_metric_catalog.private.json`。
3. 如需自定义路径，使用环境变量 `HOOGENDOORN_METRIC_CATALOG_PATH`。
4. 对外仓库只保留 Markdown 文档、示例配置和示例参数目录。

公开前建议执行两层检查：

1. `bash scripts/verify.sh privacy`
2. 如果扫描提示 Git 历史中存在私有资料，先清理历史，再公开仓库。

注意：

- 仅删除当前文件或加入 `.gitignore`，不能清掉已经提交过的历史记录。
- 如果私密文档、真实系统 ID、旧默认密码已经进入 Git 历史，公开前需要使用 `git filter-repo` 或新建一份干净的公开仓库导出代码。
- 如果真实密钥曾经提交过，即使后续删除，也应视为已经泄露，必须先轮换。
