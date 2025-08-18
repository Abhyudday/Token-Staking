#!/bin/bash

# Token Holder Bot Deployment Script
# This script helps deploy the bot to Railway

set -e

echo "🚀 Token Holder Bot - Deployment Script"
echo "========================================"

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "📁 Initializing git repository..."
    git init
    echo "✅ Git repository initialized"
else
    echo "📁 Git repository already exists"
fi

# Check git status
echo ""
echo "📊 Git Status:"
git status

# Add all files
echo ""
echo "📦 Adding files to git..."
git add .

# Check what will be committed
echo ""
echo "📋 Files to be committed:"
git diff --cached --name-only

# Commit changes
echo ""
echo "💾 Committing changes..."
read -p "Enter commit message (or press Enter for default): " commit_msg
if [ -z "$commit_msg" ]; then
    commit_msg="feat: Add Token Holder Bot with healthcheck endpoints"
fi

git commit -m "$commit_msg"

# Check if remote exists
if ! git remote get-url origin > /dev/null 2>&1; then
    echo ""
    echo "🔗 No remote origin found."
    read -p "Enter your GitHub repository URL (e.g., https://github.com/username/repo.git): " repo_url
    if [ -n "$repo_url" ]; then
        git remote add origin "$repo_url"
        echo "✅ Remote origin added: $repo_url"
    fi
fi

# Push to repository
echo ""
echo "🚀 Pushing to repository..."
if git remote get-url origin > /dev/null 2>&1; then
    # Check if main branch exists, otherwise use master
    if git show-ref --verify --quiet refs/heads/main; then
        branch="main"
    else
        branch="master"
    fi
    
    echo "📤 Pushing to $branch branch..."
    git push -u origin "$branch"
    echo "✅ Code pushed successfully!"
    
    echo ""
    echo "🎉 Deployment Summary:"
    echo "======================"
    echo "✅ Code committed and pushed to repository"
    echo "✅ Healthcheck endpoints added (/health, /)"
    echo "✅ Railway configuration ready"
    echo ""
    echo "Next steps:"
    echo "1. Connect your repository to Railway"
    echo "2. Set environment variables in Railway dashboard"
    echo "3. Deploy the application"
    echo ""
    echo "Required environment variables:"
    echo "- BOT_TOKEN"
    echo "- DATABASE_URL"
    echo "- SOLSCAN_API_KEY"
    echo "- ADMIN_USER_IDS"
    echo "- MINIMUM_USD_THRESHOLD (optional)"
    
else
    echo "⚠️ No remote origin configured. Please add your repository URL first."
    echo "Run: git remote add origin <your-repo-url>"
fi

echo ""
echo "🏁 Deployment script completed!"
