#!/bin/bash
# ARIS Database Management Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$(dirname "$SCRIPT_DIR")/docker"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Database connection helper
db_exec() {
    docker compose -f "$DOCKER_DIR/docker-compose.yml" exec aris-postgres psql -U aris -d aris_agent -c "$1"
}

db_exec_file() {
    docker compose -f "$DOCKER_DIR/docker-compose.yml" exec aris-postgres psql -U aris -d aris_agent -f "$1"
}

# Commands
case "${1:-help}" in
    "start")
        log_info "Starting PostgreSQL container..."
        cd "$DOCKER_DIR"
        docker compose up -d aris-postgres
        log_success "PostgreSQL container started"
        ;;
    
    "stop")
        log_info "Stopping PostgreSQL container..."
        cd "$DOCKER_DIR"
        docker compose stop aris-postgres
        log_success "PostgreSQL container stopped"
        ;;
    
    "restart")
        log_info "Restarting PostgreSQL container..."
        cd "$DOCKER_DIR"
        docker compose restart aris-postgres
        log_success "PostgreSQL container restarted"
        ;;
    
    "status")
        log_info "Checking PostgreSQL container status..."
        cd "$DOCKER_DIR"
        docker compose ps aris-postgres
        ;;
    
    "logs")
        log_info "Showing PostgreSQL container logs..."
        cd "$DOCKER_DIR"
        docker compose logs -f aris-postgres
        ;;
    
    "shell")
        log_info "Opening PostgreSQL shell..."
        cd "$DOCKER_DIR"
        docker compose exec aris-postgres psql -U aris -d aris_agent
        ;;
    
    "reset")
        log_warning "This will DELETE ALL DATA in the database!"
        read -p "Are you sure? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            log_info "Stopping PostgreSQL container..."
            cd "$DOCKER_DIR"
            docker compose down aris-postgres
            log_info "Removing PostgreSQL volume..."
            docker volume rm docker_aris_postgres_data 2>/dev/null || true
            log_info "Starting fresh PostgreSQL container..."
            docker compose up -d aris-postgres
            log_success "Database reset complete"
        else
            log_info "Database reset cancelled"
        fi
        ;;
    
    "backup")
        BACKUP_FILE="${2:-aris_backup_$(date +%Y%m%d_%H%M%S).sql}"
        log_info "Creating database backup: $BACKUP_FILE"
        cd "$DOCKER_DIR"
        docker compose exec aris-postgres pg_dump -U aris -d aris_agent > "$BACKUP_FILE"
        log_success "Backup created: $BACKUP_FILE"
        ;;
    
    "restore")
        if [ -z "$2" ]; then
            log_error "Usage: $0 restore <backup_file>"
            exit 1
        fi
        if [ ! -f "$2" ]; then
            log_error "Backup file not found: $2"
            exit 1
        fi
        log_warning "This will REPLACE ALL DATA in the database!"
        read -p "Are you sure? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            log_info "Restoring database from: $2"
            cd "$DOCKER_DIR"
            docker compose exec -T aris-postgres psql -U aris -d aris_agent < "$2"
            log_success "Database restored from: $2"
        else
            log_info "Database restore cancelled"
        fi
        ;;
    
    "stats")
        log_info "Database statistics:"
        db_exec "
        SELECT 
            'Chats' as table_name, COUNT(*) as count FROM chats
        UNION ALL
        SELECT 'Plans', COUNT(*) FROM plans  
        UNION ALL
        SELECT 'Actions', COUNT(*) FROM actions
        UNION ALL
        SELECT 'Memory Items', COUNT(*) FROM session_memory;
        "
        ;;
    
    "recent")
        log_info "Recent activity (last 24 hours):"
        db_exec "
        SELECT 
            c.user_id,
            p.summary,
            p.status,
            p.created_at,
            COUNT(a.id) as actions
        FROM chats c
        JOIN plans p ON c.id = p.chat_id
        LEFT JOIN actions a ON p.id = a.plan_id
        WHERE p.created_at > NOW() - INTERVAL '24 hours'
        GROUP BY c.user_id, p.summary, p.status, p.created_at
        ORDER BY p.created_at DESC
        LIMIT 10;
        "
        ;;
    
    "cleanup")
        log_info "Running database cleanup..."
        db_exec "SELECT cleanup_expired_sessions();"
        log_success "Database cleanup complete"
        ;;
    
    "help"|*)
        echo "ARIS Database Management Script"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  start          Start PostgreSQL container"
        echo "  stop           Stop PostgreSQL container"
        echo "  restart        Restart PostgreSQL container"
        echo "  status         Show container status"
        echo "  logs           Show container logs"
        echo "  shell          Open PostgreSQL shell"
        echo "  reset          Reset database (WARNING: deletes all data)"
        echo "  backup [file]  Create database backup"
        echo "  restore <file> Restore database from backup"
        echo "  stats          Show database statistics"
        echo "  recent         Show recent activity"
        echo "  cleanup        Run database cleanup (remove expired data)"
        echo "  help           Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 start                    # Start database"
        echo "  $0 shell                    # Open SQL shell"
        echo "  $0 backup my_backup.sql     # Create backup"
        echo "  $0 stats                    # Show table counts"
        ;;
esac
