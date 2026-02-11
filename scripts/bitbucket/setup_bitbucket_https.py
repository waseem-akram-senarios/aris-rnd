#!/usr/bin/env python3
"""
Setup Bitbucket Access via HTTPS
Alternative to SSH when SSH keys don't work
"""
import subprocess
import os
from pathlib import Path

def print_section(title):
    """Print section header"""
    print(f"\n{'='*60}")
    print(f"🔧 {title}")
    print('='*60)

def setup_https_remote():
    """Setup Bitbucket remote with HTTPS"""
    print_section("SETUP BITBUCKET HTTPS REMOTE")
    
    print("📋 Since SSH isn't working, let's use HTTPS instead")
    print("🔧 This uses your Bitbucket username and password")
    
    print("\n📝 Commands to add Bitbucket remote:")
    print("   git remote add bitbucket https://YOUR_USERNAME@bitbucket.org/YOUR_USERNAME/aris.git")
    print()
    print("📝 Replace YOUR_USERNAME with your actual Bitbucket username")
    print("📝 Your repository name: aris")
    
    # Get current remotes
    print("\n📋 Current remotes:")
    try:
        result = subprocess.run(['git', 'remote', '-v'], 
                              capture_output=True, text=True)
        print(result.stdout)
    except Exception as e:
        print(f"❌ Error: {e}")

def test_https_connection():
    """Test HTTPS connection to Bitbucket"""
    print_section("TEST HTTPS CONNECTION")
    
    print("🔍 Testing basic connectivity to Bitbucket...")
    
    try:
        result = subprocess.run(['git', 'ls-remote', 'https://bitbucket.org'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ HTTPS connectivity to Bitbucket works!")
            print("📝 You can use HTTPS remotes")
            return True
        else:
            print("❌ HTTPS connectivity failed")
            print(f"📝 Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error testing HTTPS: {e}")
        return False

def setup_git_credentials():
    """Setup Git credentials for HTTPS"""
    print_section("SETUP GIT CREDENTIALS")
    
    print("🔧 For HTTPS, Git needs your Bitbucket credentials")
    print("📝 Options:")
    
    print("\n1️⃣ Option 1: Credential Helper (Recommended)")
    print("   git config --global credential.helper store")
    print("   # Git will ask for username/password once and remember them")
    
    print("\n2️⃣ Option 2: Environment Variables")
    print("   export GIT_USERNAME='your-bitbucket-username'")
    print("   export GIT_PASSWORD='your-bitbucket-password' or app-password")
    
    print("\n3️⃣ Option 3: Include in URL (Not recommended for security)")
    print("   git remote add bitbucket https://username:password@bitbucket.org/username/repo.git")
    
    print("\n🔑 RECOMMENDATION: Use Bitbucket App Password")
    print("   1. Go to Bitbucket Settings → App Passwords")
    print("   2. Create app password with 'Repositories' permissions")
    print("   3. Use app password instead of regular password")

def interactive_setup():
    """Interactive setup for user"""
    print_section("INTERACTIVE SETUP")
    
    print("🚀 Let's set up Bitbucket access step by step")
    
    # Get username
    username = input("\n📝 Enter your Bitbucket username: ").strip()
    if not username:
        print("❌ Username required")
        return
    
    # Create remote command
    remote_url = f"https://{username}@bitbucket.org/{username}/aris.git"
    
    print(f"\n🔧 Command to add Bitbucket remote:")
    print(f"   git remote add bitbucket {remote_url}")
    
    # Ask if user wants to execute
    execute = input("\n🤔 Do you want to execute this command? (y/n): ").strip().lower()
    
    if execute == 'y':
        try:
            print(f"🔄 Adding Bitbucket remote...")
            result = subprocess.run(['git', 'remote', 'add', 'bitbucket', remote_url], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Bitbucket remote added successfully!")
                
                # Show new remotes
                print("\n📋 Updated remotes:")
                result = subprocess.run(['git', 'remote', '-v'], 
                                      capture_output=True, text=True)
                print(result.stdout)
                
                # Test connection
                print("\n🔍 Testing connection...")
                result = subprocess.run(['git', 'fetch', 'bitbucket'], 
                                      capture_output=True, text=True)
                
                if result.returncode == 0:
                    print("✅ Connection successful!")
                    print("🚀 You can now push to Bitbucket!")
                    print("\n📝 Commands to use:")
                    print("   git push -u bitbucket main")
                    print("   git pull bitbucket main")
                else:
                    print("❌ Connection failed - you may need to authenticate")
                    print("📝 Git will prompt for username/password")
                    print("🔑 Use your Bitbucket username and app password")
                    
            else:
                print(f"❌ Failed to add remote: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    else:
        print("📝 Command not executed. You can run it manually later.")

def main():
    """Main function"""
    print("🚀 BITBUCKET HTTPS SETUP")
    print("="*60)
    print("Setting up Bitbucket access via HTTPS (alternative to SSH)")
    
    # Test HTTPS connectivity
    if test_https_connection():
        setup_https_remote()
        setup_git_credentials()
        interactive_setup()
    else:
        print("❌ Cannot connect to Bitbucket via HTTPS")
        print("📝 Please check your internet connection")

if __name__ == "__main__":
    main()
