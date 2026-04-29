# Kaza Shop — руководство по развёртыванию и эксплуатации

## 1. Описание проекта

Kaza Shop — интернет-магазин с Telegram-ботом для покупателей и веб-панелью для администратора. Четыре Docker-сервиса: PostgreSQL, FastAPI-бэкенд, Telegram-бот (aiogram), React SPA (Vite).

**Ключевые возможности:**
- Админка (React): управление товарами (до 3 фото), категориями/подкатегориями, заказами, FAQ, импорт из Excel, статистика, настройки
- Telegram-бот: каталог с галереей фото, корзина, оформление заказа с реквизитами СБП, уведомления о статусе, очистка чата
- PDF-чеки с факсимиле, отправляемые покупателю в бот
- JWT-авторизация администратора, смена логина/пароля

---

## 2. Быстрый старт (локально)

### 2.1 Требования

- Docker 24+ и Docker Compose v2
- Свободные порты: `5432`, `8000`, `5173`
- Telegram Bot Token (получить у [@BotFather](https://t.me/BotFather))

### 2.2 Подготовка

```bash
git clone <repo-url> kaza_shop
cd kaza_shop

# Создать .env (локальная разработка)
cat > .env << 'EOF'
DB_USER=kaza_admin
DB_PASSWORD=devpassword123
DB_NAME=kaza_shop
SECRET_KEY=dev-secret-key-not-for-production
ADMIN_PASSWORD=changeme123!
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_TG_ID=123456789
PAYMENT_PROVIDER_TOKEN=
EOF

# Создать пустые директории
mkdir -p media data
```
### 2.3 Запуск

docker compose build --no-cache
docker compose up -d

### 2.4 Проверка работоспособности

curl http://localhost:8000/health          # → {"status":"ok"}
open http://localhost:5173                  # страница логина

bash

docker compose down          # контейнеры остановлены, данные сохранены
docker compose down -v       # ⚠️ полное удаление БД и медиа

## 3. Деплой на VPS
### 3.1 Подготовка сервера (Ubuntu 22.04 / 24.04)
bash

ssh root@<vps-ip>

apt update && apt upgrade -y
apt install -y docker.io docker-compose-v2 curl

systemctl enable docker
systemctl start docker

mkdir -p /opt/kaza-shop/media /opt/kaza-shop/data
cd /opt/kaza-shop

### 3.2 Файл .env для продакшена
bash
```
cat > /opt/kaza-shop/.env << 'EOF'
DB_USER=kaza_prod
DB_PASSWORD=$(openssl rand -base64 24)
DB_NAME=kaza_shop
SECRET_KEY=$(openssl rand -base64 48)
ADMIN_PASSWORD=$(openssl rand -base64 16)
BOT_TOKEN=<реальный токен от BotFather>
ADMIN_TG_ID=<числовой Telegram ID админа>
DOMAIN=shop.example.com
CORS_ORIGINS=https://shop.example.com
EOF
```
Отредактировать .env — заменить <...> реальными значениями и записать пароли отдельно.
### 3.3 Перенос кода на сервер

С локальной машины:
bash
```
rsync -av --exclude='.git' --exclude='*.log' --exclude='__pycache__' \
      --exclude='*.pyc' --exclude='.env' --exclude='media/*' \
      ./ user@<vps-ip>:/opt/kaza-shop/
```
### 3.4 Запуск
bash
```
ssh user@<vps-ip>
cd /opt/kaza-shop
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d
```
### 3.5 Nginx reverse proxy + HTTPS
bash
```
apt install -y nginx certbot python3-certbot-nginx
```
```
cat > /etc/nginx/sites-available/kaza-shop << 'NGINX'
server {
    listen 80;
    server_name shop.example.com;

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

    client_max_body_size 20M;
}
```
NGINX
```
ln -s /etc/nginx/sites-available/kaza-shop /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d shop.example.com
```
### 3.6 Проверка

    https://shop.example.com/health → {"status":"ok"}

    https://shop.example.com → страница логина в админку

    Бот в Telegram → /start → главное меню

## 4. Архитектура данных (где что хранится)
Данные	Где	Сохраняются при docker compose down
Товары, категории, подкатегории	PostgreSQL	✅ named volume postgres_data
Заказы, корзины, пользователи	PostgreSQL	✅
FAQ, настройки магазина	PostgreSQL	✅
Фото товаров	./media/ (bind mount)	✅
Факсимиле (печать)	./media/	✅
Логи приложения и бота	./media/logs/	✅
Учётные данные админа	./data/.admin_creds.json (bind mount)	✅
PDF-чеки	./media/	✅

Важно: docker compose down сохраняет все данные. Никогда не выполнять docker compose down -v на продакшене — это удалит том postgres_data и очистит базу данных.
## 5. Резервное копирование
### 5.1 Автоматический скрипт (daily cron)
bash
```
cat > /opt/kaza-shop/backup.sh << 'BACKUP'
#!/bin/bash
BACKUP_DIR=/opt/backups/kaza-shop
mkdir -p $BACKUP_DIR
DATE=$(date +%Y%m%d_%H%M%S)
```
# Дамп БД
docker compose -f /opt/kaza-shop/docker-compose.prod.yml exec -T db \
  pg_dump -U kaza_prod kaza_shop > $BACKUP_DIR/db_$DATE.sql

# Медиа-файлы
tar -czf $BACKUP_DIR/media_$DATE.tar.gz /opt/kaza-shop/media/

# Удалять резервные копии старше 30 дней
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $DATE"
BACKUP

chmod +x /opt/kaza-shop/backup.sh

Добавить в crontab (crontab -e):
text

0 3 * * * /opt/kaza-shop/backup.sh >> /var/log/kaza-backup.log 2>&1

### 5.2 Ручное резервное копирование перед обновлением
bash

ssh user@<vps-ip>
cd /opt/kaza-shop
./backup.sh

## 6. Внесение изменений в работающий сервис
### 6.1 Изменение кода бэкенда или бота (Python)
bash

# На локальной машине
git add -A && git commit -m "fix: описание правки"

# Скопировать изменённые файлы на сервер
rsync -av app/ user@<vps-ip>:/opt/kaza-shop/app/

# Перезапустить соответствующий контейнер
ssh user@<vps-ip> "cd /opt/kaza-shop && docker compose -f docker-compose.prod.yml restart app bot"

### 6.2 Изменение кода фронтенда (React)
bash

rsync -av seller-panel/src/ user@<vps-ip>:/opt/kaza-shop/seller-panel/src/
ssh user@<vps-ip> "cd /opt/kaza-shop && docker compose -f docker-compose.prod.yml restart seller"

### 6.3 Изменение Dockerfile, зависимостей или compose-файла
bash

rsync -av Dockerfile requirements.txt docker-compose.prod.yml user@<vps-ip>:/opt/kaza-shop/
ssh user@<vps-ip> "cd /opt/kaza-shop && docker compose -f docker-compose.prod.yml build --no-cache app bot seller && docker compose -f docker-compose.prod.yml up -d"

### 6.4 Изменение структуры БД (новые колонки в моделях)

Если в модели добавляются новые поля, после переноса кода необходимо пересоздать БД с миграцией данных:
bash

# 1. Сделать резервную копию
ssh user@<vps-ip> "/opt/kaza-shop/backup.sh"

# 2. Сделать дамп
ssh user@<vps-ip> "docker compose -f /opt/kaza-shop/docker-compose.prod.yml exec -T db pg_dump -U kaza_prod kaza_shop > /tmp/before_migration.sql"

# 3. Остановить, удалить том БД, пересоздать
ssh user@<vps-ip> << 'EOF'
cd /opt/kaza-shop
docker compose -f docker-compose.prod.yml down
docker volume rm kaza_shop_postgres_data
docker compose -f docker-compose.prod.yml build --no-cache app bot
docker compose -f docker-compose.prod.yml up -d
EOF

# 4. Восстановить данные из дампа
ssh user@<vps-ip> "docker compose -f /opt/kaza-shop/docker-compose.prod.yml exec -T db psql -U kaza_prod kaza_shop < /tmp/before_migration.sql"

Более надёжный способ — подключить Alembic для миграций (рекомендуется при активной разработке).
## 7. Диагностика и исправление ошибок
### 7.1 Проверка состояния всех сервисов
bash

docker compose -f docker-compose.prod.yml ps

Все контейнеры должны быть Up и healthy.
### 7.2 Логи конкретного сервиса
bash

docker compose -f docker-compose.prod.yml logs app --tail 50   # бэкенд
docker compose -f docker-compose.prod.yml logs bot --tail 50   # бот
docker compose -f docker-compose.prod.yml logs db --tail 20    # база данных

### 7.3 Частые ошибки и их решение
Симптом	Причина	Решение
Бот не отвечает	BOT_TOKEN не задан или невалиден	Проверить .env, перезапустить: docker compose restart bot
Админка не грузится / ошибка сети	Упал контейнер app	docker compose logs app --tail 50, искать ошибку импорта или БД
column ... does not exist	Добавлены новые поля в модель, но БД не обновлена	Выполнить миграцию БД (см. п. 6.4)
Фото не отображаются в боте	Не сброшен кэш каталога	В админке: Настройки → Сбросить кэш каталога
Connection refused между bot и app	Сетевой сбой Docker	docker compose restart bot
Не приходят уведомления в Telegram	Неверный admin_contact в настройках	Проверить ID через @userinfobot, указать в админке
Кнопка «Сформировать чек» не работает	fonts-dejavu-core не установлен	Пересобрать образ: docker compose build --no-cache app && docker compose up -d
### 7.4 Полный перезапуск сервиса
bash

cd /opt/kaza-shop
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d

## 8. Обновление сервиса без потери данных
Пошаговая процедура (безопасное обновление)
bash

# 1. Резервная копия
/opt/kaza-shop/backup.sh

# 2. Перенести новый код
rsync -av --exclude='.git' --exclude='*.log' ./ user@<vps-ip>:/opt/kaza-shop/

# 3. Остановить и пересоздать контейнеры (тома остаются)
ssh user@<vps-ip> << 'UPDATE'
cd /opt/kaza-shop
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml build --no-cache app bot seller
docker compose -f docker-compose.prod.yml up -d

# Проверить
docker compose -f docker-compose.prod.yml ps
curl http://localhost:8000/health
UPDATE

После этого все данные (товары, заказы, фото, настройки) сохранятся, так как:

    postgres_data — именованный том Docker, не удаляется при down

    media/ и data/ — bind-монтирования с хоста

    seller_node_modules — именованный том

## 9. Мониторинг и восстановление
### 9.1 Внешний мониторинг

Настроить UptimeRobot или аналогичный сервис на https://shop.example.com/health. При падении — алерт на Telegram или email.
### 9.2 Автоматический перезапуск

Все сервисы в docker-compose имеют restart: always — Docker автоматически перезапустит упавший контейнер в течение нескольких секунд.
### 9.3 Действия при полном падении VPS

    Убедиться, что VPS снова доступен

    Зайти по SSH

    cd /opt/kaza-shop && docker compose -f docker-compose.prod.yml up -d

    Проверить docker compose -f docker-compose.prod.yml ps

    Данные восстановятся из томов автоматически

## 10. Безопасность — чеклист

    .env не в репозитории (добавлен в .gitignore)

    SECRET_KEY заменён на случайный 64-символьный

    ADMIN_PASSWORD заменён на стойкий пароль

    CORS_ORIGINS указывает на конкретный домен

    Порт БД не открыт наружу (в docker-compose.prod.yml секция ports для db удалена или 127.0.0.1)

    Nginx + HTTPS настроен

    server.log и другие логи не лежат в репозитории

    Пароль админа изменён после первого входа

