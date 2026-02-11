#!/usr/bin/env python3
"""
Complete Bitbucket Setup Guide
Final steps to connect Git to Bitbucket
"""
import subprocess
import webbrowser
from pathlib import Path

def print_section(title):
    """Print section header"""
    print(f"\n{'='*60}")
    print(f"🔧 {title}")
    print('='*60)

def show_ssh_key():
    """Show SSH key for easy copying"""
    print_section("YOUR SSH PUBLIC KEY")
    
    ssh_key_file = Path.home() / '.ssh' / 'id_ed25519.pub'
    if ssh_key_file.exists():
        with open(ssh_key_file, 'r') as f:
            ssh_key = f.read().strip()
        
        print("🔑 Copy this entire key:")
        print("-" * 60)
        print(ssh_key)
        print("-" * 60)
        print("\n📋 Copy command for Linux:")
        print("   cat ~/.ssh/id_ed25519.pub | xclip -sel clip")
        print("\n📋 Or copy manually from above")
    else:
        print("❌ SSH key not found")

def bitbucket_setup_steps():
    """Detailed Bitbucket setup steps"""
    print_section("BITBUCKET SETUP STEPS")
    
    print("🌐 STEP 1: Go to Bitbucket")
    print("   URL: https://bitbucket.org")
    print("   Login with your credentials")
    
    print("\n👤 STEP 2: Go to Settings")
    print("   Click your profile picture (top right)")
    print("   Select 'Settings' from dropdown")
    
    print("\n🔑 STEP 3: Add SSH Key")
    print("   Click 'SSH Keys' in left menu")
    print("   Click 'Add key' button")
    print("   Fill in:")
    print("   - Label: Development Machine")
    print("   - Key: [Paste the SSH key from above]")
    print("   Click 'Add key'")
    
    print("\n✅ STEP 4: Verify Key Added")
    print("   You should see your SSH key in the list")
    print("   Status should show 'Active'")

def test_connection_after_setup():
    """Test connection after user adds key"""
    print_section("TEST CONNECTION")
    
    print("🔍 After adding the SSH key, let's test the connection...")
    input("\nPress Enter after you've added the SSH key to Bitbucket...")
    
    try:
        print("🔄 Testing SSH connection...")
        result = subprocess.run(['ssh', '-T', 'git@bitbucket.org'], 
                              capture_output=True, text=True, timeout=15)
        
        print(f"📝 Return code: {result.returncode}")
        print(f"📝 Stdout: {result.stdout}")
        print(f"📝 Stderr: {result.stderr}")
        
        if result.returncode == 1 and 'logged in as' in result.stderr.lower():
            print("✅ SUCCESS: SSH connection working!")
            return True
        elif result.returncode == 1 and 'permission denied' in result.stderr.lower():
            print("❌ ISSUE: Permission denied - SSH key not properly added")
            print("📝 Please check:")
            print("   1. SSH key was copied correctly")
            print("   2. SSH key was added to correct Bitbucket account")
            print("   3. No extra spaces or newlines in the key")
            return False
        else:
            print("⚠️ UNEXPECTED RESPONSE")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Connection timeout")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def setup_bitbucket_remote():
    """Setup Bitbucket remote"""
    print_section("ADD BITBUCKET REMOTE")
    
    print("📋 Your current repository name: aris")
    print("🔧 Replace YOUR_USERNAME with your actual Bitbucket username")
    
    print("\n📝 Commands to run:")
    print("   # Add Bitbucket remote (SSH)")
    print("   git remote add bitbucket git@bitbucket.org:YOUR_USERNAME/aris.git")
    print()
    print("   # Or add Bitbucket remote (HTTPS)")
    print("   git remote add bitbucket https://YOUR_USERNAME@bitbucket.org/YOUR_USERNAME/aris.git")
    print()
    print("   # Verify remote added")
    print("   git remote -v")
    print()
    print("   # Test connection")
    print("   git fetch bitbucket")
    print()
    print("   # Push to Bitbucket")
    print("   git push -u bitbucket main")

def troubleshoot():
    """Troubleshooting tips"""
    print_section("TROUBLESHOOTING")
    
    print("❌ If SSH key doesn't work:")
    print("   1. Double-check the SSH key was copied exactly")
    print("   2. Ensure no extra spaces or newlines")
    print("   3. Try removing and re-adding the SSH key")
    print("   4. Check you're logged into correct Bitbucket account")
    
    print("\n❌ If connection times out:")
    print("   1. Check internet connection")
    print("   2. Try HTTPS instead of SSH")
    print("   3. Check firewall settings")
    
    print("\n❌ If permission denied:")
    print("   1. SSH key not added to Bitbucket")
    print("   2. Wrong SSH key (different from what's in Bitbucket)")
    print("   3. Bitbucket account issue")

def main():
    """Main function"""
    print("🚀 COMPLETE BITBUCKET GIT SETUP")
    print("="*60)
    print("Since you can login to Bitbucket via UI, let's complete the Git setup!")
    
    # Show SSH key
    show_ssh_key()
    
    # Setup steps
    bitbucket_setup_steps()
    
    # Test connection
    if test_connection_after_setup():
        setup_bitbucket_remote()
        
        print_section("🎉 SETUP COMPLETE!")
        print("✅ SSH key added to Bitbucket")
        print("✅ Connection tested successfully")
        print("✅ Ready to add remote and push code")
        
        print("\n🚀 Next Steps:")
        print("1. Add Bitbucket remote (commands shown above)")
        print("2. Push your code to Bitbucket")
        print("3. Enjoy Git operations with Bitbucket!")
        
    else:
        troubleshoot()
        print("\n🔄 Try the setup again after fixing the issues")

if __name__ == "__main__":
    main()
