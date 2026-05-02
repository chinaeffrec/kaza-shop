# Kaza Shop — расширенный runbook для техподдержки

Документ для инженеров поддержки и DevOps: диагностика, восстановление, обновления, риски и контрольные точки.

## 1. Контекст и ответственность

- Окружение: production VPS (Ubuntu 22.04/24.04), Docker Compose.
- Критичные данные: PostgreSQL, `/opt/kaza-shop/media`, `/opt/kaza-shop/data`, `/opt/kaza-shop/.env`.
- Любые изменения сначала на backup, затем на production.

## 2. Быстрые команды (шпаргалка)

```bash
cd /opt/kaza-shop

docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs app --tail 200
docker compose -f docker-compose.prod.yml logs bot --tail 200
docker compose -f docker-compose.prod.yml logs db --tail 200

curl -fsS http://localhost:8000/health
```

## 3. Диагностика инцидента (порядок)

1. Проверить доступность сервиса:
- `curl http://localhost:8000/health`
- открывается ли админка.

2. Проверить контейнеры:
- `docker compose ... ps`
- статус `Up` / `Exited` / `Restarting`.

3. Проверить логи:
- `app` -> API/миграции/ошибки runtime;
- `bot` -> Telegram API, polling;
- `db` -> отказ БД/коррупция/аутентификация.

4. Проверить ресурсы хоста:

```bash
free -h
df -h
docker system df
```

5. Проверить сеть и DNS:

```bash
curl -I https://api.telegram.org
getent hosts api.telegram.org
```

## 4. Стандартные сценарии и действия

### 4.1 Бот не отвечает

Проверить:
- `BOT_TOKEN` в `.env`;
- доступ к `api.telegram.org`;
- логи `bot`.

Действия:

```bash
cd /opt/kaza-shop
docker compose -f docker-compose.prod.yml restart bot
```

### 4.2 Админка не открывается

Проверить:
- контейнер seller;
- Nginx (если используется);
- firewall.

```bash
docker compose -f docker-compose.prod.yml ps
systemctl status nginx
nginx -t
ufw status
```

### 4.3 API недоступен/ошибки 5xx

Проверить `app` и `db` логи, затем:

```bash
cd /opt/kaza-shop
docker compose -f docker-compose.prod.yml restart app
docker compose -f docker-compose.prod.yml restart db
```

## 5. Полный перезапуск (без удаления данных)

```bash
cd /opt/kaza-shop
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

Никогда не использовать `down -v` в production.

## 6. Backup политика

- Backup: ежедневно (cron 03:00).
- Хранение: минимум 30 дней.
- Минимум раз в месяц тест восстановления.

Проверка наличия backup:

```bash
ls -lah /opt/backups/kaza-shop/
```

## 7. Disaster Recovery (полная процедура)

1. Остановить сервис:

```bash
cd /opt/kaza-shop
docker compose -f docker-compose.prod.yml down
```

2. Восстановить конфиг/сервисные файлы:

```bash
tar -xzf /opt/backups/kaza-shop/config_YYYYMMDD_HHMMSS.tar.gz -C /
```

3. Восстановить медиа:

```bash
tar -xzf /opt/backups/kaza-shop/media_YYYYMMDD_HHMMSS.tar.gz -C /opt/kaza-shop
```

4. Поднять БД и восстановить дамп:

```bash
docker compose -f /opt/kaza-shop/docker-compose.prod.yml up -d db
cat /opt/backups/kaza-shop/db_YYYYMMDD_HHMMSS.sql | \
  docker compose -f /opt/kaza-shop/docker-compose.prod.yml exec -T db \
  psql -U kaza_prod -d kaza_shop
```

5. Поднять весь сервис:

```bash
docker compose -f /opt/kaza-shop/docker-compose.prod.yml up -d
```

6. Выполнить smoke-тест (см. раздел 10 в `README.md`).

## 8. Обновление production

### Безопасный порядок

1. Backup.
2. Доставка новой версии (rsync/scp).
3. Сборка сервисов.
4. `up -d`.
5. Smoke-тест.

```bash
cd /opt/kaza-shop
./backup.sh
docker compose -f docker-compose.prod.yml build app bot seller
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
curl -fsS http://localhost:8000/health
```

### Откат

Если после обновления критическая ошибка:
- вернуть предыдущую версию файлов;
- выполнить `docker compose ... up -d`;
- при необходимости восстановить из backup.

## 9. Безопасность и hardening

- `.env` только `chmod 600`.
- Порт `5432` не публиковать наружу.
- Firewall: только `22/80/443`.
- HTTPS обязателен для боевого домена.
- SSH: отключить парольный вход, использовать ключи.
- Рекомендуется `fail2ban`.

## 10. Контрольный чеклист on-call

Перед завершением инцидента убедиться:

- `health` = ok.
- Админка доступна.
- Бот отвечает на `/start`.
- Тестовое уведомление о заказе приходит.
- Свежий backup успешно создается.
- В журнале инцидента сохранены причина и действия.

## 11. Запрещенные действия

- `docker compose down -v`
- удаление `/opt/kaza-shop/.env`
- ручная чистка `/opt/kaza-shop/media` без backup
- смена DB-пароля в `.env` без синхронизации с БД

## 12. Эскалация

Эскалировать разработчику, если:
- повторяющиеся 5xx без явной причины;
- ошибки миграций/схемы БД;
- повреждение backup;
- отказ восстановления по процедуре DR.
