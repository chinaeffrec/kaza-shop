#!/usr/bin/env bash
# Kaza Shop — Обновление до новой версии
# Использование: bash update.sh
# Обновление с сохранением всех данных, бэкапом перед обновлением,
# автооткатом при неудаче.
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${INSTALL_DIR}/.env" 2>/dev/null || true

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
info() { echo -e "${BLUE}→${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*"; }

ALERT_BOT_TOKEN="${ALERT_BOT_TOKEN:-${BOT_TOKEN:-}}"
ALERT_CHAT_ID="${ALERT_CHAT_ID:-${ADMIN_TG_ID:-}}"

send_telegram() {
    local text="$1"
    [[ -z "$ALERT_BOT_TOKEN" || -z "$ALERT_CHAT_ID" ]] && return 0
    curl -sf "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${ALERT_CHAT_ID}" -d "parse_mode=HTML" \
        --data-urlencode "text=${text}" >/dev/null 2>&1 || true
}

echo -e "\n${BOLD}Kaza Shop — Обновление${NC}"
echo "────────────────────────────────────────"

[[ "$EUID" -ne 0 ]] && { err "Запустите от root: sudo bash update.sh"; exit 1; }

cd "$INSTALL_DIR"

# ── Шаг 1: Бэкап перед обновлением ───────────────────────────────────────────
info "Создаём бэкап перед обновлением..."
if bash "${INSTALL_DIR}/backup.sh" >/dev/null 2>&1; then
    ok "Бэкап создан"
else
    warn "Бэкап не создан. Продолжить всё равно? (y/N): "
    read -r C; [[ "$C" =~ ^[Yy]$ ]] || exit 1
fi

# ── Шаг 2: Сохраняем состояние ДО изменений (для отката) ─────────────────────
OLD_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "")
OLD_IMAGE=$(docker compose -f docker-compose.prod.yml images -q app 2>/dev/null | head -1 || echo "")
if [[ -n "$OLD_IMAGE" ]]; then
    docker tag "$OLD_IMAGE" kaza_rollback:pre-update 2>/dev/null && \
        ok "Образ сохранён для отката: kaza_rollback:pre-update" || true
fi

# ── Шаг 3: Получение обновлений ───────────────────────────────────────────────
info "Получаем обновления..."
if git pull origin main 2>/dev/null; then
    NEW_VERSION=$(git describe --tags --always 2>/dev/null || date +%Y%m%d)
    ok "Код обновлён до версии: ${NEW_VERSION}"
else
    warn "Git не настроен или нет новых версий. Пересобираем текущий код..."
fi

# ── Шаг 4: Сборка новых образов ───────────────────────────────────────────────
info "Собираем образы (без остановки сервиса)..."
docker compose -f docker-compose.prod.yml build --no-cache
ok "Образы собраны"

# ── Шаг 5 (бывший 4): Rolling restart ────────────────────────────────────────
info "Применяем обновление..."
ROLLBACK_IMAGE="kaza_rollback:pre-update"  # тегирован до сборки

docker compose -f docker-compose.prod.yml up -d --remove-orphans

# ── Шаг 6: Проверка после обновления ─────────────────────────────────────────
info "Проверяем работоспособность..."
sleep 10
for i in $(seq 1 6); do
    HTTP=$(curl -sf -o /dev/null -w "%{http_code}" \
        --max-time 10 "http://localhost:8000/health" 2>/dev/null || echo "000")
    if [[ "$HTTP" == "200" ]]; then
        ok "Сервис работает корректно"
        send_telegram "✅ <b>Обновление завершено</b>%0A%0AВерсия: ${NEW_VERSION:-текущая}%0AМагазин работает нормально."
        echo ""
        echo -e "${GREEN}${BOLD}Обновление выполнено успешно!${NC}"
        exit 0
    fi
    warn "Попытка ${i}/6: HTTP ${HTTP}, ждём 10 сек..."
    sleep 10
done

# ── Откат ─────────────────────────────────────────────────────────────────────
err "Сервис не ответил после обновления. Выполняем откат..."
send_telegram "🔴 <b>Ошибка обновления</b>%0A%0AВыполняется откат к предыдущей версии..."

docker compose -f docker-compose.prod.yml down
# Откат кода (если был git pull)
if [[ -n "$OLD_COMMIT" ]]; then
    git reset --hard "$OLD_COMMIT" 2>/dev/null && \
        info "Код откачен к коммиту ${OLD_COMMIT:0:8}" || true
fi
# Откат образа: пересобираем из старого кода
if docker image inspect kaza_rollback:pre-update &>/dev/null 2>&1; then
    docker tag kaza_rollback:pre-update \
        "$(docker compose -f docker-compose.prod.yml config --images 2>/dev/null | head -1 || echo kaza_shop_app)" \
        2>/dev/null || true
fi
docker compose -f docker-compose.prod.yml up -d

sleep 15
ROLLBACK_CHECK=$(curl -sf -o /dev/null -w "%{http_code}" \
    --max-time 10 "http://localhost:8000/health" 2>/dev/null || echo "000")
if [[ "$ROLLBACK_CHECK" == "200" ]]; then
    warn "Откат выполнен. Сервис работает на предыдущей версии."
    send_telegram "⚠️ <b>Откат выполнен</b>%0A%0AСервис восстановлен на предыдущей версии.%0AОбновление не применено."
else
    err "Откат не помог. Требуется ручное вмешательство."
    send_telegram "🆘 <b>Критическая ошибка</b>%0A%0AОбновление и откат не удались.%0AТребуется ручное вмешательство.%0A%0AВыполните бэкап вручную и обратитесь в поддержку."
fi
