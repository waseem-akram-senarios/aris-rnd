#!/bin/bash
# Manual Git Push Script
# Run this script to push your code to GitHub

echo "=========================================="
echo "GIT PUSH TO REMOTE"
echo "=========================================="
echo ""

cd /home/senarios/Desktop/aris

echo "Current branch:"
git branch --show-current

echo ""
echo "Commits ready to push:"
git log origin/main..HEAD --oneline 2>/dev/null || git log --oneline -5

echo ""
echo "=========================================="
echo "Attempting to push to remote..."
echo "=========================================="
echo ""

# Try to push
git push origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ SUCCESS! Code pushed to GitHub"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "❌ PUSH FAILED - Authentication Required"
    echo "=========================================="
    echo ""
    echo "Please authenticate using one of these methods:"
    echo ""
    echo "1. SSH Key (if configured):"
    echo "   git push origin main"
    echo ""
    echo "2. Personal Access Token:"
    echo "   git push https://YOUR_TOKEN@github.com/waseem-intelycx/aris-rnd.git main"
    echo ""
    echo "3. GitHub CLI (if installed):"
    echo "   gh auth login"
    echo "   git push origin main"
    echo ""
    echo "4. Use your IDE's Git push feature"
    echo ""
fi
