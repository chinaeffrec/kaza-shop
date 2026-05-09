#!/usr/bin/env bash
# Kaza Shop — Автоматический бэкап БД + медиафайлов
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${INSTALL_DIR}/.env" 2>/dev/null || true

BACKUP_DIR="${INSTALL_DIR}/backups"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="kaza_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')] BACKUP"

send_telegram() {
    local text="$1"
    [[ -z "${ALERT_BOT_TOKEN:-}" || -z "${ALERT_CHAT_ID:-}" ]] && return 0
    curl -sf "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${ALERT_CHAT_ID}" \
        -d "parse_mode=HTML" \
        -d "text=${text}" >/dev/null 2>&1 || true
}

echo "${LOG_PREFIX}: Начало бэкапа ${BACKUP_NAME}"
mkdir -p "${BACKUP_PATH}"

# ── БД ────────────────────────────────────────────────────────────────────────
echo "${LOG_PREFIX}: Дамп базы данных..."
if docker compose -f "${INSTALL_DIR}/docker-compose.prod.yml" exec -T db \
    pg_dump -U "${DB_USER:-kaza_user}" "${DB_NAME:-kaza_shop}" \
    --no-password 2>/dev/null \
    > "${BACKUP_PATH}/database.sql"; then
    DB_SIZE=$(du -sh "${BACKUP_PATH}/database.sql" | cut -f1)
    echo "${LOG_PREFIX}: БД сохранена (${DB_SIZE})"
else
    echo "${LOG_PREFIX}: ОШИБКА дампа БД"
    send_telegram "⚠️ <b>Бэкап не выполнен</b>%0A%0AНе удалось создать дамп базы данных.%0AПроверьте состояние сервиса: docker compose ps"
    exit 1
fi

# ── Медиафайлы ─────────────────────────────────────────────────────────────────
echo "${LOG_PREFIX}: Архивирование медиафайлов..."
if [[ -d "${INSTALL_DIR}/media" ]]; then
    tar -czf "${BACKUP_PATH}/media.tar.gz" \
        -C "${INSTALL_DIR}" media/ 2>/dev/null || true
    MEDIA_SIZE=$(du -sh "${BACKUP_PATH}/media.tar.gz" 2>/dev/null | cut -f1 || echo "0")
    echo "${LOG_PREFIX}: Медиафайлы сохранены (${MEDIA_SIZE})"
fi

# ── .env (зашифровать или просто скопировать) ──────────────────────────────────
cp "${INSTALL_DIR}/.env" "${BACKUP_PATH}/.env.backup"
chmod 600 "${BACKUP_PATH}/.env.backup"

# ── Итоговый архив ─────────────────────────────────────────────────────────────
ARCHIVE="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
tar -czf "$ARCHIVE" -C "${BACKUP_DIR}" "${BACKUP_NAME}/"
rm -rf "${BACKUP_PATH}"

TOTAL_SIZE=$(du -sh "$ARCHIVE" | cut -f1)
echo "${LOG_PREFIX}: Архив создан: ${ARCHIVE} (${TOTAL_SIZE})"

# ── Удаление старых бэкапов ────────────────────────────────────────────────────
DELETED=$(find "${BACKUP_DIR}" -name "kaza_backup_*.tar.gz" \
    -mtime "+${KEEP_DAYS}" -delete -print | wc -l)
[[ "$DELETED" -gt 0 ]] && echo "${LOG_PREFIX}: Удалено старых бэкапов: ${DELETED}"

# ── Статистика хранилища ───────────────────────────────────────────────────────
BACKUP_COUNT=$(find "${BACKUP_DIR}" -name "kaza_backup_*.tar.gz" | wc -l)
BACKUP_TOTAL=$(du -sh "${BACKUP_DIR}" | cut -f1)

echo "${LOG_PREFIX}: Итого бэкапов: ${BACKUP_COUNT} (${BACKUP_TOTAL})"

# ── Уведомление ────────────────────────────────────────────────────────────────
send_telegram "✅ <b>Бэкап выполнен</b>%0A%0AРазмер: ${TOTAL_SIZE}%0AБэкапов всего: ${BACKUP_COUNT} (${BACKUP_TOTAL})%0AХранится ${KEEP_DAYS} дней"

echo "${LOG_PREFIX}: Завершено успешно"
