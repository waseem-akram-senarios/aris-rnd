# Email Driver System

The Intelycx Email MCP Server now features a Laravel-style email driver system that supports multiple email backends with a unified interface.

## 🚀 **Driver Types**

### **1. SES Driver (`ses`)**
Uses Amazon Simple Email Service for reliable, scalable email delivery.

**Configuration:**
```bash
EMAIL_DRIVER=ses
EMAIL_REGION=us-east-1
EMAIL_SENDER=noreply@intelycx.com
EMAIL_SENDER_NAME=Intelycx ARIS

# AWS Credentials (optional if using IAM roles)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

**Features:**
- ✅ High deliverability and reputation
- ✅ Bounce and complaint handling
- ✅ Sending statistics and monitoring
- ✅ Attachment support up to 10MB
- ✅ HTML and plain text emails

### **2. SMTP Driver (`smtp`)**
Uses standard SMTP for connecting to any email server.

**Configuration:**
```bash
EMAIL_DRIVER=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_password
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT=30
EMAIL_SENDER=your_email@gmail.com
EMAIL_SENDER_NAME=Your Name
```

**Features:**
- ✅ Works with any SMTP server (Gmail, Outlook, etc.)
- ✅ TLS/SSL encryption support
- ✅ Authentication with username/password
- ✅ Attachment support
- ✅ Connection timeout configuration

### **3. Log Driver (`log`)**
Logs emails instead of sending them - perfect for development and testing.

**Configuration:**
```bash
EMAIL_DRIVER=log
EMAIL_LOG_LEVEL=INFO
EMAIL_LOG_FILE=/tmp/emails.log
EMAIL_LOG_INCLUDE_BODY=true
EMAIL_LOG_INCLUDE_ATTACHMENTS=true
EMAIL_LOG_PRETTY_PRINT=true
```

**Features:**
- ✅ No external dependencies
- ✅ Pretty-printed email logs
- ✅ File or console logging
- ✅ Configurable detail level
- ✅ Perfect for testing

## 📧 **Enhanced Email Features**

### **Attachment Support**
```python
# Download attachments from URLs
send_email(
    to="user@example.com",
    subject="Report with Attachments",
    body="Please find the attached reports.",
    attachment_urls=[
        "https://example.com/report.pdf",
        "https://example.com/data.xlsx"
    ]
)
```

### **Priority Levels**
```python
from drivers import EmailPriority

send_email(
    to="urgent@example.com",
    subject="Critical Alert",
    body="Immediate attention required!",
    priority=EmailPriority.URGENT
)
```

### **Rich Recipients**
```python
# Multiple recipient formats supported
send_email(
    to=[
        "simple@example.com",
        {"email": "user@example.com", "name": "John Doe"}
    ],
    cc=["manager@example.com"],
    bcc=["archive@example.com"],
    subject="Team Update",
    body="<h1>Important Update</h1>",
    is_html=True,
    reply_to="support@example.com"
)
```

## 🔧 **Driver Configuration**

### **Automatic Driver Selection**
The system automatically selects the best driver based on available configuration:

1. **SES Driver** - If `EMAIL_SENDER` and `EMAIL_REGION` are configured
2. **SMTP Driver** - If `SMTP_USER` and `SMTP_PASSWORD` are configured  
3. **Log Driver** - Default fallback (no credentials required)

### **Manual Driver Selection**
Override automatic selection with the `EMAIL_DRIVER` environment variable:

```bash
# Force specific driver
EMAIL_DRIVER=ses    # Use SES even if SMTP is configured
EMAIL_DRIVER=smtp   # Use SMTP even if SES is configured
EMAIL_DRIVER=log    # Force log driver for testing
```

## 🛠️ **Development & Testing**

### **Testing Drivers**
Use the `test_email_driver` tool to verify configuration:

```python
# Via MCP tool
test_email_driver()

# Returns:
{
    "success": true,
    "driver_info": {
        "driver_name": "log",
        "driver_class": "LogDriver"
    },
    "connection_test": true,
    "configuration_status": "configured"
}
```

### **Development Setup**
For development, use the log driver:

```bash
# .env file for development
EMAIL_DRIVER=log
EMAIL_LOG_FILE=/tmp/aris_emails.log
EMAIL_LOG_PRETTY_PRINT=true
```

### **Production Setup**
For production, use SES or SMTP:

```bash
# Production with SES
EMAIL_DRIVER=ses
EMAIL_REGION=us-east-1
EMAIL_SENDER=noreply@yourcompany.com
EMAIL_SENDER_NAME=Your Company ARIS

# Production with SMTP
EMAIL_DRIVER=smtp
SMTP_HOST=your-smtp-server.com
SMTP_PORT=587
SMTP_USER=aris@yourcompany.com
SMTP_PASSWORD=secure_password
SMTP_USE_TLS=true
```

## 📊 **Comparison with Old Agent**

| Feature | Old Agent | New Driver System | Enhancement |
|---------|-----------|------------------|-------------|
| **Email Backend** | ✅ SES only | ✅ SES + SMTP + Log | **3x more options** |
| **Attachments** | ✅ File-based | ✅ URL-based + File-based | **Enhanced flexibility** |
| **Configuration** | ❌ Hardcoded | ✅ Environment-driven | **Laravel-style config** |
| **Testing** | ❌ No test mode | ✅ Log driver for testing | **Better dev experience** |
| **Error Handling** | ✅ Basic | ✅ Driver-specific errors | **Enhanced diagnostics** |
| **Priority Support** | ❌ No priority | ✅ 4 priority levels | **New feature** |
| **Validation** | ❌ Basic | ✅ Pydantic validation | **Type safety** |
| **Monitoring** | ❌ Limited | ✅ Rich metadata & logging | **Better observability** |

## 🎯 **Key Improvements**

### **✅ Laravel-Style Architecture**
- **Driver abstraction** - Switch email backends without code changes
- **Environment configuration** - All settings via environment variables
- **Factory pattern** - Clean driver instantiation and management

### **✅ Enhanced Functionality** 
- **Attachment downloads** - Automatically download and attach files from URLs
- **Priority levels** - Support for low/normal/high/urgent priority emails
- **Rich recipients** - Support for display names and multiple formats
- **Custom headers** - Add custom email headers for tracking/routing

### **✅ Better Development Experience**
- **Log driver** - Test email functionality without sending real emails
- **Driver testing** - Built-in connectivity and configuration testing
- **Rich diagnostics** - Detailed error messages and status information
- **Backward compatibility** - Existing code continues to work

## 🔄 **Migration from Old Agent**

The new system is a **complete enhancement** of the old agent's email capabilities:

- **✅ SES functionality preserved** - All SES features from old agent work
- **✅ Enhanced error handling** - Better error messages and recovery
- **✅ New features added** - Attachments, priorities, multiple drivers
- **✅ Better architecture** - Modular, testable, and maintainable

The email system is now **production-ready** with enterprise-grade features and follows modern design patterns.
