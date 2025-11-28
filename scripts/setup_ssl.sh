#!/bin/bash

# SSL Certificate Setup Script for ARIS RAG System
# This script sets up SSL certificates using Let's Encrypt (certbot)
# Falls back to self-signed certificates for testing if Let's Encrypt fails

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
NGINX_DIR="$PROJECT_ROOT/nginx"
SSL_DIR="$NGINX_DIR/ssl"
DOMAIN="${1:-}"  # Domain name as first argument
EMAIL="${2:-admin@example.com}"  # Email for Let's Encrypt (optional)

echo "==================================================================="
echo "  SSL Certificate Setup for ARIS RAG System"
echo "==================================================================="
echo ""

# Check if running as root (needed for certbot)
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  Warning: This script should be run as root/sudo for Let's Encrypt"
    echo "   For self-signed certificates, you can run without root"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    USE_SUDO=""
else
    USE_SUDO=""
fi

# Create SSL directory if it doesn't exist
mkdir -p "$SSL_DIR"

# Function to generate self-signed certificate
generate_self_signed() {
    echo "🔐 Generating self-signed SSL certificate..."
    echo ""
    
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$SSL_DIR/key.pem" \
        -out "$SSL_DIR/cert.pem" \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=${DOMAIN:-localhost}" \
        2>/dev/null || {
        echo "❌ Error: openssl not found. Please install openssl:"
        echo "   Ubuntu/Debian: sudo apt-get install openssl"
        echo "   CentOS/RHEL: sudo yum install openssl"
        exit 1
    }
    
    chmod 600 "$SSL_DIR/key.pem"
    chmod 644 "$SSL_DIR/cert.pem"
    
    echo "✅ Self-signed certificate generated:"
    echo "   Certificate: $SSL_DIR/cert.pem"
    echo "   Private Key: $SSL_DIR/key.pem"
    echo ""
    echo "⚠️  Note: Self-signed certificates will show security warnings in browsers"
    echo "   This is suitable for testing/internal use only"
}

# Function to setup Let's Encrypt certificate
setup_letsencrypt() {
    if [ -z "$DOMAIN" ]; then
        echo "❌ Error: Domain name required for Let's Encrypt"
        echo "   Usage: $0 <domain-name> [email]"
        echo "   Example: $0 example.com admin@example.com"
        exit 1
    fi
    
    echo "🔐 Setting up Let's Encrypt SSL certificate for: $DOMAIN"
    echo ""
    
    # Check if certbot is installed
    if ! command -v certbot &> /dev/null; then
        echo "📦 Installing certbot..."
        if command -v apt-get &> /dev/null; then
            $USE_SUDO apt-get update
            $USE_SUDO apt-get install -y certbot
        elif command -v yum &> /dev/null; then
            $USE_SUDO yum install -y certbot
        else
            echo "❌ Error: Cannot install certbot automatically"
            echo "   Please install certbot manually: https://certbot.eff.org/"
            exit 1
        fi
    fi
    
    # Create directory for ACME challenge
    mkdir -p /var/www/certbot
    
    # Stop nginx if running (certbot needs port 80)
    echo "🛑 Stopping nginx (if running)..."
    $USE_SUDO docker-compose -f "$PROJECT_ROOT/docker-compose.prod.yml" stop nginx 2>/dev/null || true
    $USE_SUDO systemctl stop nginx 2>/dev/null || true
    
    # Generate certificate
    echo "📜 Requesting certificate from Let's Encrypt..."
    $USE_SUDO certbot certonly --standalone \
        --preferred-challenges http \
        -d "$DOMAIN" \
        --email "$EMAIL" \
        --agree-tos \
        --non-interactive \
        --cert-path "$SSL_DIR/cert.pem" \
        --key-path "$SSL_DIR/key.pem" || {
        echo ""
        echo "❌ Let's Encrypt certificate generation failed"
        echo "   Common reasons:"
        echo "   - Domain not pointing to this server"
        echo "   - Port 80 not accessible from internet"
        echo "   - Firewall blocking port 80"
        echo ""
        read -p "Generate self-signed certificate instead? (y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            generate_self_signed
            return
        else
            exit 1
        fi
    }
    
    # Copy certificates to nginx ssl directory
    CERT_PATH="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
    KEY_PATH="/etc/letsencrypt/live/$DOMAIN/privkey.pem"
    
    if [ -f "$CERT_PATH" ] && [ -f "$KEY_PATH" ]; then
        $USE_SUDO cp "$CERT_PATH" "$SSL_DIR/cert.pem"
        $USE_SUDO cp "$KEY_PATH" "$SSL_DIR/key.pem"
        $USE_SUDO chmod 644 "$SSL_DIR/cert.pem"
        $USE_SUDO chmod 600 "$SSL_DIR/key.pem"
        
        echo "✅ Let's Encrypt certificate installed:"
        echo "   Certificate: $SSL_DIR/cert.pem"
        echo "   Private Key: $SSL_DIR/key.pem"
    else
        echo "❌ Error: Certificate files not found"
        exit 1
    fi
    
    # Setup auto-renewal
    echo ""
    echo "🔄 Setting up automatic certificate renewal..."
    
    # Create renewal script
    RENEWAL_SCRIPT="/etc/cron.monthly/renew-aris-ssl"
    $USE_SUDO tee "$RENEWAL_SCRIPT" > /dev/null <<EOF
#!/bin/bash
certbot renew --quiet --deploy-hook "docker-compose -f $PROJECT_ROOT/docker-compose.prod.yml restart nginx"
EOF
    
    $USE_SUDO chmod +x "$RENEWAL_SCRIPT"
    
    echo "✅ Auto-renewal configured (runs monthly via cron)"
}

# Main logic
echo "Select SSL certificate type:"
echo "  1) Let's Encrypt (free, requires domain and port 80 access)"
echo "  2) Self-signed (for testing/internal use)"
echo ""
read -p "Enter choice [1-2]: " choice

case $choice in
    1)
        setup_letsencrypt
        ;;
    2)
        generate_self_signed
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "==================================================================="
echo "  SSL Setup Complete"
echo "==================================================================="
echo ""
echo "📋 Next steps:"
echo "   1. Review nginx configuration: $NGINX_DIR/nginx.conf"
echo "   2. Start the application: docker-compose -f docker-compose.prod.yml up -d"
echo "   3. Test HTTPS: https://${DOMAIN:-localhost}"
echo ""

