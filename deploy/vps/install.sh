#!/usr/bin/env bash
# ClaimRadar BG - install or update on a fresh Ubuntu/Debian VPS (Docker + Caddy HTTPS).
#
# One command (as root, or with sudo):
#   curl -fsSL https://raw.githubusercontent.com/biramentv-ux/claimradar-bg/main/deploy/vps/install.sh | sudo bash
#
# Optional settings, passed as environment variables after sudo:
#   curl -fsSL .../install.sh | sudo DOMAIN=claimradar.dyrakarmy.eu OPENAI_API_KEY=sk-... bash
#
#   DOMAIN          public host name           (default: claimradar.dyrakarmy.eu)
#   OPENAI_API_KEY  enables AI verdicts        (optional)
#   DATABASE_URL    Supabase/Postgres URL      (optional, JSONL fallback otherwise)
#   OWNER_KEY / ADMIN_KEY  reuse existing admin keys (otherwise generated)
#   INSTALL_DIR     checkout location          (default: /opt/claimradar-bg)
#   BRANCH          git branch                 (default: main)
#
# Running it again updates the code (git pull) and rebuilds; .env is kept.

set -euo pipefail

DOMAIN="${DOMAIN:-claimradar.dyrakarmy.eu}"
REPO_URL="${REPO_URL:-https://github.com/biramentv-ux/claimradar-bg.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/claimradar-bg}"
BRANCH="${BRANCH:-main}"
COMPOSE_FILE="deploy/vps/docker-compose.yml"

log()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m OK\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m !!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mERR\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run as root (use: ... | sudo bash)."
command -v apt-get >/dev/null 2>&1 || die "This installer supports Ubuntu/Debian (apt-get) only."

rand_key() { openssl rand -base64 48 | tr -d '\n=+/' | cut -c1-"${1:-43}"; }

# 1. Base packages + Docker
log "Installing base packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl git openssl >/dev/null

if ! command -v docker >/dev/null 2>&1; then
    log "Installing Docker (official get.docker.com script)..."
    curl -fsSL https://get.docker.com | sh >/dev/null
fi
systemctl enable --now docker >/dev/null 2>&1 || true
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin is missing after install."
ok "Docker $(docker --version | awk '{print $3}' | tr -d ,)"

# 2. Swap on small servers (the Python image build and Whisper need memory)
mem_mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
if [ "$mem_mb" -lt 3500 ] && ! swapon --show | grep -q .; then
    log "RAM is ${mem_mb} MB - adding a 2 GB swap file..."
    fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
    chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
    grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    ok "Swap enabled"
fi

# 3. Code
if [ -d "$INSTALL_DIR/.git" ]; then
    log "Updating code in $INSTALL_DIR..."
    git -C "$INSTALL_DIR" fetch -q --depth 1 origin "$BRANCH"
    git -C "$INSTALL_DIR" reset -q --hard "origin/$BRANCH"
else
    log "Cloning $REPO_URL into $INSTALL_DIR..."
    git clone -q --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"
ok "Code at $(git rev-parse --short HEAD)"

# 4. .env (created once, then kept; secrets never leave this server)
ROOT_DOMAIN="${DOMAIN#*.}"
case "$ROOT_DOMAIN" in *.*) ;; *) ROOT_DOMAIN="$DOMAIN" ;; esac

set_env() {  # set_env KEY VALUE  -> add or replace a line in .env
    local key="$1" value="$2"
    if grep -q "^${key}=" .env; then
        local escaped
        escaped=$(printf '%s' "$value" | sed -e 's/[\/&|]/\\&/g')
        sed -i "s|^${key}=.*|${key}=${escaped}|" .env
    else
        printf '%s=%s\n' "$key" "$value" >> .env
    fi
}

if [ ! -f .env ]; then
    log "Creating .env with generated secrets..."
    umask 077
    cat > .env <<EOF
# ClaimRadar BG production settings - generated $(date -u +%Y-%m-%dT%H:%M:%SZ)
DOMAIN=$DOMAIN
PUBLIC_BASE_URL=https://$DOMAIN
CUSTOM_DOMAIN=$DOMAIN
ROOT_DOMAIN=$ROOT_DOMAIN
AUTH_ENABLED=1
OWNER_KEY=${OWNER_KEY:-$(rand_key)}
ADMIN_KEY=${ADMIN_KEY:-$(rand_key)}
AUTH_TOKEN_SALT=$(rand_key 64)
RATE_LIMIT_HASH_SALT=$(rand_key 64)
RATE_LIMIT_ENABLED=1
DB_ENABLED=1
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
OWASP_FRAME_ANCESTORS="'self'"
SECURITY_FRAME_ANCESTORS="'self'"
EOF
else
    log "Keeping existing .env (domain settings refreshed)"
    set_env DOMAIN "$DOMAIN"
    set_env PUBLIC_BASE_URL "https://$DOMAIN"
    set_env CUSTOM_DOMAIN "$DOMAIN"
    set_env ROOT_DOMAIN "$ROOT_DOMAIN"
fi
[ -n "${OPENAI_API_KEY:-}" ] && set_env OPENAI_API_KEY "$OPENAI_API_KEY"
[ -n "${DATABASE_URL:-}" ] && set_env DATABASE_URL "$DATABASE_URL"
chmod 600 .env
ok ".env ready ($INSTALL_DIR/.env, mode 600)"

# 5. Firewall (only if ufw is active)
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
    ufw allow OpenSSH >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; ufw allow 443/udp >/dev/null
    ok "ufw: 22, 80, 443 open"
fi

# Oracle Cloud Ubuntu images ship iptables rules that REJECT everything but SSH,
# even with ufw inactive. Open 80/443 before that REJECT rule and persist it.
if command -v iptables >/dev/null 2>&1 && iptables -S INPUT 2>/dev/null | grep -q -- "-j REJECT"; then
    for port in 80 443; do
        iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null \
            || iptables -I INPUT 1 -p tcp --dport "$port" -j ACCEPT
    done
    iptables -C INPUT -p udp --dport 443 -j ACCEPT 2>/dev/null \
        || iptables -I INPUT 1 -p udp --dport 443 -j ACCEPT
    if command -v netfilter-persistent >/dev/null 2>&1; then
        netfilter-persistent save >/dev/null 2>&1 || true
    fi
    ok "iptables: 80, 443 open (Oracle-style REJECT rules detected)"
    warn "Oracle Cloud: also open TCP 80 and 443 in the VCN Security List (Ingress, 0.0.0.0/0)."
fi

# 6. DNS check
SERVER_IP=$(curl -fsS -4 --max-time 10 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')
DNS_IP=$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk 'NR==1 {print $1}')
if [ -n "$DNS_IP" ] && [ "$DNS_IP" = "$SERVER_IP" ]; then
    ok "DNS: $DOMAIN -> $SERVER_IP"
    DNS_OK=1
else
    warn "DNS: $DOMAIN -> ${DNS_IP:-<none>}, but this server is $SERVER_IP"
    warn "Add an A record: ${DOMAIN%%.*} -> $SERVER_IP  (HTTPS starts automatically once it resolves)"
    DNS_OK=0
fi

# 7. Build and start
log "Building and starting (first build takes 5-15 minutes)..."
docker compose -f "$COMPOSE_FILE" --env-file .env up -d --build --remove-orphans

log "Waiting for the app to become healthy..."
app_id=$(docker compose -f "$COMPOSE_FILE" --env-file .env ps -q app)
status="starting"
for _ in $(seq 1 90); do
    status=$(docker inspect -f '{{.State.Health.Status}}' "$app_id" 2>/dev/null || echo "unknown")
    [ "$status" = "healthy" ] && break
    [ "$status" = "unhealthy" ] && break
    sleep 10
done

if [ "$status" != "healthy" ]; then
    warn "App status: $status. Last log lines:"
    docker compose -f "$COMPOSE_FILE" --env-file .env logs --tail 40 app || true
    die "The app did not become healthy. Fix the error above, then run this command again."
fi
ok "App is healthy"

if [ "$DNS_OK" = "1" ]; then
    for _ in $(seq 1 12); do
        code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "https://$DOMAIN/health" || true)
        [ "$code" = "200" ] && break
        sleep 10
    done
    if [ "$code" = "200" ]; then ok "https://$DOMAIN/health -> 200"; else warn "HTTPS not ready yet (got $code); Caddy keeps retrying the certificate."; fi
fi

cat <<EOF

========================================================
 ClaimRadar BG is running.
   Site:        https://$DOMAIN   (http://$SERVER_IP works only after DNS)
   Admin keys:  grep -E '^(OWNER|ADMIN)_KEY' $INSTALL_DIR/.env
   Logs:        cd $INSTALL_DIR && docker compose -f $COMPOSE_FILE logs -f app
   Update:      run the same install command again
========================================================
EOF
