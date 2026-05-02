# Kaza Shop — краткая инструкция для клиента

Этот документ — короткий чеклист запуска и базовой эксплуатации.

## 1. Что нужно заранее

- VPS на Ubuntu 24.04 (рекомендуется, вне РФ).
- Домен (желательно, для HTTPS).
- Telegram Bot Token от `@BotFather`.
- Ваш Telegram ID от `@userinfobot`.

## 2. Быстрый запуск

1. Подготовьте сервер:

```bash
apt update && apt upgrade -y
apt install -y docker.io docker-compose-v2 curl rsync
systemctl enable docker && systemctl start docker
mkdir -p /opt/kaza-shop/media /opt/kaza-shop/data
```

2. Загрузите проект в `/opt/kaza-shop`.

3. Создайте `/opt/kaza-shop/.env`:

```env
DB_USER=kaza_prod
DB_PASSWORD=СЛОЖНЫЙ_ПАРОЛЬ
DB_NAME=kaza_shop
SECRET_KEY=ДЛИННЫЙ_СЛУЧАЙНЫЙ_КЛЮЧ
ADMIN_PASSWORD=СЛОЖНЫЙ_ПАРОЛЬ_АДМИНА
BOT_TOKEN=ТОКЕН_ОТ_BOTFATHER
ADMIN_TG_ID=ВАШ_TELEGRAM_ID
DOMAIN=shop.example.com
CORS_ORIGINS=https://shop.example.com
```

4. Запустите сервис:

```bash
cd /opt/kaza-shop
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d
```

## 3. Проверка после запуска

```bash
docker compose -f docker-compose.prod.yml ps
curl http://localhost:8000/health
```

Должно быть:
- контейнеры `Up`;
- `/health` -> `{"status":"ok"}`.

Админка: `http://<IP_СЕРВЕРА>:5173`  
Логин: `admin`  
Пароль: `ADMIN_PASSWORD` из `.env`

## 4. Обязательные действия после первого входа

- Сменить пароль администратора.
- Проверить, что бот отвечает на `/start`.
- Сделать тестовый заказ и проверить уведомление.
- Настроить HTTPS (если есть домен).
- Настроить backup (ежедневно).

## 5. Обновление версии

```bash
cd /opt/kaza-shop && ./backup.sh
# загрузите новые файлы проекта
cd /opt/kaza-shop
docker compose -f docker-compose.prod.yml build app bot seller
docker compose -f docker-compose.prod.yml up -d
```

## 6. Что нельзя делать

- Не выполнять `docker compose down -v`.
- Не удалять `.env`.
- Не открывать наружу порт `5432`.
- Не обновлять сервис без резервной копии.

## 7. Где подробная инструкция

Полная версия с восстановлением и прод-практиками: [README.md](./README.md)
