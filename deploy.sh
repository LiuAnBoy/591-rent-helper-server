#!/bin/bash

# ============================================
# 591 Crawler Deployment Script
# ============================================
# Usage:
#   ./deploy.sh          # Auto detect: first run or update
#   ./deploy.sh init     # Force first-time setup
#   ./deploy.sh update   # Force update mode
#   ./deploy.sh migrate  # Run migrations only
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect docker compose command (v2: "docker compose" vs v1: "docker-compose")
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif docker-compose version &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "Error: docker compose not found. Please install Docker."
    exit 1
fi

# Load environment variables from .env if exists
load_env() {
    if [ -f ".env" ]; then
        set -a
        . .env
        set +a
    fi
}

# Database connection variables (with defaults)
get_db_user() { echo "${PG_USER:-postgres}"; }
get_db_name() { echo "${PG_DATABASE:-rent591}"; }

# ============================================
# Helper Functions
# ============================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if this is first run (no .env file or no postgres data)
is_first_run() {
    if [ ! -f ".env" ]; then
        return 0  # true, is first run
    fi
    
    # Check if postgres container has data
    if ! docker volume ls | grep -q "591-crawler_postgres_data"; then
        return 0  # true, is first run
    fi
    
    return 1  # false, not first run
}

# Wait for PostgreSQL to be ready
wait_for_postgres() {
    load_env
    local db_user=$(get_db_user)

    log_info "Waiting for PostgreSQL to be ready..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if $DOCKER_COMPOSE exec -T postgres pg_isready -U "$db_user" > /dev/null 2>&1; then
            log_success "PostgreSQL is ready!"
            return 0
        fi
        echo -n "."
        sleep 1
        ((attempt++))
    done

    log_error "PostgreSQL failed to start after ${max_attempts} seconds"
    return 1
}

# ============================================
# Environment Setup
# ============================================

setup_env() {
    if [ ! -f ".env" ]; then
        log_info "Creating .env from .env.example..."
        cp .env.example .env
        log_warn "Please edit .env with your configuration!"
        log_warn "Especially: TELEGRAM_BOT_TOKEN, JWT_SECRET"
        echo ""
        read -p "Press Enter after editing .env to continue, or Ctrl+C to abort..."
    else
        log_info ".env file already exists"
    fi
}

# ============================================
# Migration Functions
# ============================================

# Ensure schema_migrations table exists
ensure_migration_table() {
    load_env
    local db_user=$(get_db_user)
    local db_name=$(get_db_name)

    log_info "Ensuring migration tracking table exists..."
    $DOCKER_COMPOSE exec -T postgres psql -U "$db_user" -d "$db_name" << 'SQL'
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) UNIQUE NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
SQL
}

# Get list of applied migrations
get_applied_migrations() {
    load_env
    local db_user=$(get_db_user)
    local db_name=$(get_db_name)

    $DOCKER_COMPOSE exec -T postgres psql -U "$db_user" -d "$db_name" -t -A -c \
        "SELECT filename FROM schema_migrations ORDER BY filename;" 2>/dev/null || echo ""
}

# Run a single migration file
run_migration() {
    load_env
    local db_user=$(get_db_user)
    local db_name=$(get_db_name)
    local migration_file="$1"
    local filename=$(basename "$migration_file")

    log_info "Running migration: $filename"

    # Run the migration
    if $DOCKER_COMPOSE exec -T postgres psql -U "$db_user" -d "$db_name" < "$migration_file"; then
        # Record the migration
        $DOCKER_COMPOSE exec -T postgres psql -U "$db_user" -d "$db_name" -c \
            "INSERT INTO schema_migrations (filename) VALUES ('$filename') ON CONFLICT DO NOTHING;"
        log_success "Migration $filename completed"
        return 0
    else
        log_error "Migration $filename failed!"
        return 1
    fi
}

# Run pending migrations
run_migrations() {
    log_info "Checking for pending migrations..."
    
    ensure_migration_table
    
    local applied=$(get_applied_migrations)
    local pending_count=0
    
    # Find all .sql files in migrations folder, sorted by name
    for migration_file in $(find migrations -name "*.sql" -type f | sort); do
        local filename=$(basename "$migration_file")
        
        # Skip if already applied
        if echo "$applied" | grep -q "^${filename}$"; then
            log_info "Skipping (already applied): $filename"
            continue
        fi
        
        # Run the migration
        run_migration "$migration_file"
        ((pending_count++))
    done
    
    if [ $pending_count -eq 0 ]; then
        log_info "No pending migrations"
    else
        log_success "Applied $pending_count migration(s)"
    fi
}

# ============================================
# First-time Setup
# ============================================

first_time_setup() {
    log_info "=========================================="
    log_info "First-time Setup"
    log_info "=========================================="
    
    # Setup environment
    setup_env
    
    # Start all services
    log_info "Starting all services..."
    $DOCKER_COMPOSE up -d
    
    # Wait for postgres
    wait_for_postgres
    
    # Run all migrations
    run_migrations
    
    log_success "=========================================="
    log_success "First-time setup complete!"
    log_success "=========================================="
    log_info "Services running:"
    $DOCKER_COMPOSE ps
}

# ============================================
# Git Functions
# ============================================

git_pull() {
    log_info "Pulling latest changes from git..."

    # Check if this is a git repo
    if [ ! -d ".git" ]; then
        log_warn "Not a git repository, skipping git pull"
        return 0
    fi

    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        log_warn "You have uncommitted changes!"
        read -p "Continue anyway? (y/N): " confirm
        if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
            log_error "Aborted by user"
            exit 1
        fi
    fi

    # Pull latest
    if git pull; then
        log_success "Git pull completed"
    else
        log_error "Git pull failed!"
        exit 1
    fi
}

# ============================================
# Update Deployment
# ============================================

update_deployment() {
    log_info "=========================================="
    log_info "Update Deployment"
    log_info "=========================================="

    # Pull latest code
    git_pull

    # Ensure postgres and redis are running
    log_info "Ensuring database services are running..."
    $DOCKER_COMPOSE up -d postgres redis

    # Wait for postgres
    wait_for_postgres

    # Run pending migrations
    run_migrations

    # Rebuild and restart app only
    log_info "Rebuilding app container..."
    $DOCKER_COMPOSE build app

    log_info "Restarting app container..."
    $DOCKER_COMPOSE up -d --no-deps app

    log_success "=========================================="
    log_success "Update complete!"
    log_success "=========================================="
    log_info "Services running:"
    $DOCKER_COMPOSE ps
}

# ============================================
# Main
# ============================================

main() {
    local mode="${1:-auto}"
    
    echo ""
    echo "======================================"
    echo "  591 Crawler Deployment Script"
    echo "======================================"
    echo ""
    
    case "$mode" in
        init)
            first_time_setup
            ;;
        update)
            update_deployment
            ;;
        migrate)
            wait_for_postgres
            run_migrations
            ;;
        auto)
            if is_first_run; then
                log_info "Detected first-time setup..."
                first_time_setup
            else
                log_info "Detected existing installation, running update..."
                update_deployment
            fi
            ;;
        *)
            echo "Usage: $0 [init|update|migrate|auto]"
            echo ""
            echo "  init    - First-time setup (create .env, start all, run all migrations)"
            echo "  update  - Update deployment (run new migrations, rebuild app)"
            echo "  migrate - Run pending migrations only"
            echo "  auto    - Auto detect mode (default)"
            exit 1
            ;;
    esac
}

main "$@"
