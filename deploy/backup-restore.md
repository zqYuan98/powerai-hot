# 备份与恢复

worker 每天 03:30 执行 `pg_dump -Fc`，文件在 `deploy/backups/powerai-YYYYMMDD-HHMM.dump`，保留 `BACKUP_KEEP_DAYS` 天。
建议再用云盘/对象存储同步该目录做异地备份。

手动备份：

    docker compose -f deploy/compose.yml exec worker python -m app.cli backup

恢复（会覆盖现有数据，先停 api/worker）：

    docker compose -f deploy/compose.yml stop api worker
    docker compose -f deploy/compose.yml exec -T db pg_restore -U powerai -d powerai --clean --if-exists < deploy/backups/<文件>.dump
    docker compose -f deploy/compose.yml start api worker
