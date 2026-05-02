# Kaza Shop — инструкция по развертыванию и эксплуатации

Эта инструкция рассчитана на самостоятельный запуск сервиса на Ubuntu VPS.

## 1. Системные требования

| Компонент | Минимально | Рекомендуется |
|---|---:|---:|
| ОС | Ubuntu 22.04/24.04 | Ubuntu 24.04 LTS |
| RAM | 1 GB | 2 GB |
| Диск | 10 GB | 20 GB SSD |
| Docker | 24+ | последняя стабильная |
| Docker Compose | v2 | v2 |
| Домен | не обязателен | обязательно (HTTPS) |
| VPS | вне РФ | Европа (DE/NL/SE) |

## 2. Важно про размещение VPS

Telegram API (`api.telegram.org`) может быть недоступен из РФ. Для стабильной работы бота размещайте сервер за пределами РФ.

## 3. Подготовка сервера

Выполняйте команды от `root` (или через `sudo`).

```bash
apt update && apt upgrade -y
apt install -y docker.io docker-compose-v2 curl rsync ufw nginx certbot python3-certbot-nginx

systemctl enable docker
systemctl start docker

mkdir -p /opt/kaza-shop/media /opt/kaza-shop/data
cd /opt/kaza-shop
```

## 4. Базовая защита сервера (обязательно)

Откройте только нужные порты:

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status
```

Ожидаемо открыты только `22`, `80`, `443`.

## 5. Переменные окружения (`.env`)

Создайте файл:

```bash
nano /opt/kaza-shop/.env
```

Пример:

```env
DB_USER=kaza_prod
DB_PASSWORD=CHANGE_ME_STRONG_DB_PASSWORD
DB_NAME=kaza_shop
SECRET_KEY=CHANGE_ME_LONG_RANDOM_SECRET_KEY
ADMIN_PASSWORD=CHANGE_ME_STRONG_ADMIN_PASSWORD
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_TG_ID=123456789
DOMAIN=shop.example.com
CORS_ORIGINS=https://shop.example.com
```

Сгенерировать стойкие значения:

```bash
openssl rand -base64 24   # DB_PASSWORD
openssl rand -base64 48   # SECRET_KEY
openssl rand -base64 16   # ADMIN_PASSWORD
```

Ограничьте доступ к `.env`:

```bash
chmod 600 /opt/kaza-shop/.env
```

## 6. Как получить BOT_TOKEN и ADMIN_TG_ID

- `BOT_TOKEN`: в Telegram через `@BotFather` -> `/newbot`.
- `ADMIN_TG_ID`: в Telegram через `@userinfobot` (числовой ID).

## 7. Загрузка проекта на сервер

С локальной машины (из папки проекта):

```bash
rsync -av --delete \
  --exclude='.git' --exclude='.idea' --exclude='.venv' \
  --exclude='*.log' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.env' --exclude='media/*' --exclude='data/*' \
  ./ user@vps-ip:/opt/kaza-shop/
```

## 8. Первый запуск

```bash
ssh user@vps-ip
cd /opt/kaza-shop

docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d
```

Проверка:

```bash
docker compose -f docker-compose.prod.yml ps
curl http://localhost:8000/health
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173
```

Ожидаемо:
- контейнеры `Up` (и `healthy`, если healthcheck задан);
- `/health` возвращает `{"status":"ok"}`;
- порт админки отдает `200`.

Вход в админку: `http://<SERVER_IP>:5173`, логин `admin`, пароль из `ADMIN_PASSWORD`.

## 9. Домен и HTTPS через Nginx (рекомендуется)

Создайте конфиг:

```bash
nano /etc/nginx/sites-available/kaza-shop
```

```nginx
server {
    listen 80;
    server_name shop.example.com;

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    location /api/ {
        rewrite ^/api/(.*) /$1 break;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
}
```

Активируйте:

```bash
ln -sf /etc/nginx/sites-available/kaza-shop /etc/nginx/sites-enabled/kaza-shop
nginx -t && systemctl reload nginx
certbot --nginx -d shop.example.com
```

Проверка:

```bash
curl -I https://shop.example.com
curl https://shop.example.com/health
```

## 10. Smoke-тест после запуска (обязательно)

1. Открыть админку, авторизоваться.
2. Проверить вкладки: `Товары`, `Заказы`, `Статистика`, `Настройки`.
3. Создать тестовый товар (или импортировать 1-2 позиции).
4. Проверить, что бот отвечает на `/start`.
5. Оформить тестовый заказ и убедиться, что:
   - заказ появился в админке;
   - админу пришло уведомление;
   - (если настроено) чек формируется.
6. Проверить экспорт Excel в статистике.

## 11. Где хранятся данные

| Данные | Где хранятся | Сохраняются при пересборке |
|---|---|---|
| Товары, категории, заказы, настройки | PostgreSQL volume | Да |
| Фото товаров, QR, печать, чеки | `/opt/kaza-shop/media/` | Да |
| Креды админа | `/opt/kaza-shop/data/` | Да |
| Секреты | `/opt/kaza-shop/.env` | Да |

## 12. Резервное копирование

Создайте скрипт:

```bash
nano /opt/kaza-shop/backup.sh
```

```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR=/opt/backups/kaza-shop
PROJECT_DIR=/opt/kaza-shop
mkdir -p "$BACKUP_DIR"
DATE=$(date +%Y%m%d_%H%M%S)

# База данных
docker compose -f "$PROJECT_DIR/docker-compose.prod.yml" exec -T db \
  pg_dump -U kaza_prod kaza_shop > "$BACKUP_DIR/db_$DATE.sql"

# Медиа
[ -d "$PROJECT_DIR/media" ] && tar -czf "$BACKUP_DIR/media_$DATE.tar.gz" -C "$PROJECT_DIR" media

# Конфиг и сервисные данные
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" "$PROJECT_DIR/.env" "$PROJECT_DIR/data"

# Ротация (30 дней)
find "$BACKUP_DIR" -type f -mtime +30 -delete

echo "Backup completed: $DATE"
```

```bash
chmod +x /opt/kaza-shop/backup.sh
```

Первый тестовый запуск:

```bash
cd /opt/kaza-shop && ./backup.sh
ls -la /opt/backups/kaza-shop/
```

Ожидаемо есть файлы `db_*.sql`, `media_*.tar.gz`, `config_*.tar.gz`.

Cron (ежедневно в 03:00):

```bash
crontab -e
```

```cron
0 3 * * * /opt/kaza-shop/backup.sh >> /var/log/kaza-backup.log 2>&1
```

## 13. Восстановление из бэкапа (Disaster Recovery)

1. Остановить сервис:

```bash
cd /opt/kaza-shop
docker compose -f docker-compose.prod.yml down
```

2. Восстановить медиа и конфиг:

```bash
tar -xzf /opt/backups/kaza-shop/config_YYYYMMDD_HHMMSS.tar.gz -C /
tar -xzf /opt/backups/kaza-shop/media_YYYYMMDD_HHMMSS.tar.gz -C /opt/kaza-shop
```

3. Поднять только БД и дождаться готовности:

```bash
docker compose -f docker-compose.prod.yml up -d db
```

4. Восстановить БД:

```bash
cat /opt/backups/kaza-shop/db_YYYYMMDD_HHMMSS.sql | \
  docker compose -f /opt/kaza-shop/docker-compose.prod.yml exec -T db \
  psql -U kaza_prod -d kaza_shop
```

5. Поднять сервис:

```bash
docker compose -f /opt/kaza-shop/docker-compose.prod.yml up -d
```

6. Проверить `health` и вход в админку.

## 14. Обновление сервиса на новую версию

Перед обновлением сделайте backup:

```bash
cd /opt/kaza-shop && ./backup.sh
```

Загрузите новую версию (см. раздел 7), затем:

```bash
cd /opt/kaza-shop
docker compose -f docker-compose.prod.yml build app bot seller
docker compose -f docker-compose.prod.yml up -d
```

Проверка:

```bash
docker compose -f docker-compose.prod.yml ps
curl http://localhost:8000/health
```

## 15. Если сервис упал

Диагностика:

```bash
cd /opt/kaza-shop
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs app --tail 100
docker compose -f docker-compose.prod.yml logs bot --tail 100
docker compose -f docker-compose.prod.yml logs db --tail 100
```

Точечный перезапуск:

```bash
docker compose -f docker-compose.prod.yml restart app
# или bot / db
```

Полный перезапуск (без `-v`):

```bash
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

## 16. Что нельзя делать

- Не выполнять `docker compose down -v` (удаляет БД).
- Не удалять `/opt/kaza-shop/.env`.
- Не открывать наружу порт `5432`.
- Не хранить `.env` в Git/облачных публичных папках.
- Не обновлять сервис без свежего backup.

## 17. Чеклист безопасности

- `SECRET_KEY` уникальный и длинный.
- `ADMIN_PASSWORD` и `DB_PASSWORD` стойкие.
- Пароль админа сменен после первого входа.
- Включен HTTPS.
- Настроен backup + проверено восстановление.
- На firewall открыты только `22/80/443`.
- VPS размещен вне РФ для стабильной работы Telegram.

## 18. Контакты поддержки

- Telegram: `@your_username`
- Email: `support@example.com`
- Канал обновлений: `@kaza_shop`
