# Security Best Practices

## 🔒 Security Overview

This repository follows security best practices to protect sensitive information.

## ✅ Security Measures Implemented

### 1. Environment Variables
- All API keys and credentials are stored in `.env` file (not tracked in git)
- Code uses `os.getenv()` to load credentials from environment variables
- No hardcoded credentials in source code

### 2. .gitignore Protection
The `.gitignore` file includes comprehensive patterns to exclude:
- Environment files (`.env`, `.env.*`)
- API keys and credentials files
- SSH keys and certificates (`*.pem`, `*.key`)
- Server configuration files
- AWS credentials
- Temporary and cache files
- Vector stores and databases

### 3. Code Security
- ✅ No hardcoded API keys
- ✅ No hardcoded passwords
- ✅ No hardcoded tokens
- ✅ All credentials loaded from environment variables
- ✅ Proper error handling for missing credentials

## 🚫 What Should NEVER Be Committed

- `.env` files
- API keys (OpenAI, Cerebras, AWS)
- SSH private keys (`*.pem`, `id_rsa`, etc.)
- AWS credentials
- Passwords or secrets
- Server IP addresses or connection details
- Database credentials

## 📝 Setting Up Credentials

1. Create a `.env` file in the project root:
   ```bash
   cp .env.example .env  # If example exists
   # OR create manually
   ```

2. Add your credentials to `.env`:
   ```env
   OPENAI_API_KEY=your_key_here
   CEREBRAS_API_KEY=your_key_here
   
   # Optional: AWS Textract
   AWS_ACCESS_KEY_ID=your_key
   AWS_SECRET_ACCESS_KEY=your_secret
   AWS_REGION=us-east-1
   ```

3. Verify `.env` is in `.gitignore`:
   ```bash
   git check-ignore .env
   # Should output: .env
   ```

## 🔍 Security Audit Checklist

Before pushing to git, verify:
- [ ] `.env` file is not tracked
- [ ] No `.pem` files are tracked
- [ ] No hardcoded credentials in code
- [ ] All API keys use `os.getenv()`
- [ ] Server IPs/connection details removed from README
- [ ] `.gitignore` includes all sensitive file patterns

## 🛡️ If Credentials Are Exposed

If you accidentally commit sensitive data:

1. **Immediately rotate/revoke the exposed credentials**
2. Remove from git history (requires force push):
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch .env" \
     --prune-empty --tag-name-filter cat -- --all
   ```
3. Force push (⚠️ coordinate with team):
   ```bash
   git push origin --force --all
   ```

## 📚 Additional Resources

- [GitHub Security Best Practices](https://docs.github.com/en/code-security)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/secrets.html)

