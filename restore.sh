#!/usr/bin/env bash
# Kaza Shop — Восстановление из бэкапа
# Использование: bash restore.sh [путь_к_архиву]
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${INSTALL_DIR}/.env" 2>/dev/null || true

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
info() { echo -e "${BLUE}→${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*"; exit 1; }

[[ "$EUID" -ne 0 ]] && err "Запустите от root: sudo bash restore.sh"

BACKUP_DIR="${INSTALL_DIR}/backups"

# Выбор бэкапа
if [[ -n "${1:-}" && -f "$1" ]]; then
    ARCHIVE="$1"
else
    echo -e "\n${BOLD}Доступные бэкапы:${NC}"
    BACKUPS=($(find "$BACKUP_DIR" -name "kaza_backup_*.tar.gz" | sort -r))
    if [[ ${#BACKUPS[@]} -eq 0 ]]; then
        err "Бэкапы не найдены в ${BACKUP_DIR}"
    fi
    for i in "${!BACKUPS[@]}"; do
        SIZE=$(du -sh "${BACKUPS[$i]}" | cut -f1)
        DATE=$(echo "${BACKUPS[$i]}" | grep -oP '\d{8}_\d{6}' | \
            sed 's/\(\d\{4\}\)\(\d\{2\}\)\(\d\{2\}\)_\(\d\{2\}\)\(\d\{2\}\)\(\d\{2\}\)/\3.\2.\1 \4:\5:\6/' || \
            echo "")
        echo "  [$i] ${BACKUPS[$i]##*/} (${SIZE})"
    done
    echo ""
    read -rp "Выберите номер бэкапа: " IDX
    ARCHIVE="${BACKUPS[$IDX]}"
fi

[[ ! -f "$ARCHIVE" ]] && err "Файл не найден: $ARCHIVE"
ok "Бэкап: $ARCHIVE"

echo ""
warn "ВНИМАНИЕ: текущие данные будут заменены данными из бэкапа!"
read -rp "Вы уверены? Введите YES для подтверждения: " CONFIRM
[[ "$CONFIRM" == "YES" ]] || { info "Отменено."; exit 0; }

# ── Распаковка ────────────────────────────────────────────────────────────────
TMP_DIR=$(mktemp -d)
info "Распаковываем архив..."
tar -xzf "$ARCHIVE" -C "$TMP_DIR"
BACKUP_CONTENT=$(find "$TMP_DIR" -maxdepth 1 -type d | tail -1)

# ── Остановка сервисов ────────────────────────────────────────────────────────
info "Останавливаем сервисы..."
cd "$INSTALL_DIR"
docker compose -f docker-compose.prod.yml stop app bot

# ── Восстановление БД ─────────────────────────────────────────────────────────
if [[ -f "${BACKUP_CONTENT}/database.sql" ]]; then
    info "Восстанавливаем базу данных..."
    docker compose -f docker-compose.prod.yml exec -T db \
        psql -U "${DB_USER:-kaza_user}" "${DB_NAME:-kaza_shop}" \
        --no-password --single-transaction --set ON_ERROR_STOP=1 \
        < "${BACKUP_CONTENT}/database.sql"
    ok "БД восстановлена"
fi

# ── Восстановление медиафайлов ────────────────────────────────────────────────
if [[ -f "${BACKUP_CONTENT}/media.tar.gz" ]]; then
    info "Восстанавливаем медиафайлы..."
    tar -xzf "${BACKUP_CONTENT}/media.tar.gz" -C "${INSTALL_DIR}/"
    ok "Медиафайлы восстановлены"
fi

# ── Запуск ────────────────────────────────────────────────────────────────────
info "Запускаем сервисы..."
docker compose -f docker-compose.prod.yml up -d
sleep 10

HTTP=$(curl -sf -o /dev/null -w "%{http_code}" \
    --max-time 10 "http://localhost:8000/health" 2>/dev/null || echo "000")
if [[ "$HTTP" == "200" ]]; then
    ok "Сервис работает. Восстановление завершено."
else
    warn "Сервис не ответил (HTTP ${HTTP}). Проверьте логи:"
    warn "  docker compose -f docker-compose.prod.yml logs app"
fi

rm -rf "$TMP_DIR"
