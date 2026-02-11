#!/usr/bin/env python3
"""
Setup Bitbucket Git Access
Step-by-step guide to connect Git to Bitbucket
"""
import subprocess
import webbrowser
from pathlib import Path

def print_step(step_num, title, description=""):
    """Print formatted step"""
    print(f"\n{'='*60}")
    print(f"🔧 STEP {step_num}: {title}")
    print('='*60)
    if description:
        print(f"📝 {description}")

def check_ssh_key():
    """Check and display SSH key"""
    print_step(1, "Get Your SSH Public Key", 
               "Copy this SSH key and add it to your Bitbucket account")
    
    ssh_key_file = Path.home() / '.ssh' / 'id_ed25519.pub'
    if ssh_key_file.exists():
        with open(ssh_key_file, 'r') as f:
            ssh_key = f.read().strip()
        
        print("🔑 Your SSH Public Key:")
        print("-" * 40)
        print(ssh_key)
        print("-" * 40)
        print("\n✅ SSH key found and ready!")
        return ssh_key
    else:
        print("❌ No SSH key found. Creating one...")
        return create_ssh_key()

def create_ssh_key():
    """Create new SSH key"""
    try:
        subprocess.run(['ssh-keygen', '-t', 'ed25519', '-C', 'waseem@aidevlab.com', 
                       '-f', str(Path.home() / '.ssh' / 'id_ed25519'), '-N', ''],
                      check=True, capture_output=True)
        
        ssh_key_file = Path.home() / '.ssh' / 'id_ed25519.pub'
        with open(ssh_key_file, 'r') as f:
            ssh_key = f.read().strip()
        
        print("🔑 New SSH Key Created:")
        print("-" * 40)
        print(ssh_key)
        print("-" * 40)
        return ssh_key
    except Exception as e:
        print(f"❌ Error creating SSH key: {e}")
        return None

def guide_bitbucket_setup():
    """Guide user through Bitbucket setup"""
    print_step(2, "Add SSH Key to Bitbucket", 
               "Follow these steps in your Bitbucket account")
    
    print("🌐 Instructions:")
    print("1. Open Bitbucket in your browser: https://bitbucket.org")
    print("2. Click on your profile picture → Settings")
    print("3. Click on 'SSH Keys' in the left menu")
    print("4. Click 'Add key'")
    print("5. Give it a label (e.g., 'Development Machine')")
    print("6. Paste the SSH key from Step 1")
    print("7. Click 'Add key'")
    
    print("\n📋 Quick Copy Command:")
    print("   cat ~/.ssh/id_ed25519.pub | pbcopy  # macOS")
    print("   cat ~/.ssh/id_ed25519.pub | xclip -sel clip  # Linux")
    print("   cat ~/.ssh/id_ed25519.pub  # Then copy manually")

def test_ssh_connection():
    """Test SSH connection to Bitbucket"""
    print_step(3, "Test SSH Connection to Bitbucket")
    
    try:
        print("🔍 Testing SSH connection to Bitbucket...")
        result = subprocess.run(['ssh', '-T', 'git@bitbucket.org'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 1:
            # Bitbucket returns 1 for successful auth (but shows success message)
            if 'logged in as' in result.stderr.lower() or 'you can use git' in result.stderr.lower():
                print("✅ SSH connection successful!")
                print(f"📝 Response: {result.stderr.strip()}")
                return True
            else:
                print("❌ SSH connection failed")
                print(f"📝 Error: {result.stderr.strip()}")
                return False
        else:
            print("✅ SSH connection successful!")
            print(f"📝 Response: {result.stderr.strip()}")
            return True
            
    except subprocess.TimeoutExpired:
        print("❌ SSH connection timeout")
        return False
    except Exception as e:
        print(f"❌ SSH connection error: {e}")
        return False

def setup_bitbucket_remote():
    """Setup Bitbucket remote for current repository"""
    print_step(4, "Add Bitbucket Remote to Repository")
    
    print("📋 Current Git Remotes:")
    try:
        result = subprocess.run(['git', 'remote', '-v'], 
                              capture_output=True, text=True)
        print(result.stdout)
    except Exception as e:
        print(f"❌ Error checking remotes: {e}")
    
    print("\n🔧 To add Bitbucket remote, run:")
    print("   git remote add bitbucket git@bitbucket.org:YOUR_USERNAME/YOUR_REPO.git")
    print("   git remote add bitbucket https://YOUR_USERNAME@bitbucket.org/YOUR_USERNAME/YOUR_REPO.git")
    
    print("\n📝 Replace YOUR_USERNAME with your Bitbucket username")
    print("📝 Replace YOUR_REPO with your repository name")
    
    # Get current repo info
    try:
        result = subprocess.run(['git', 'rev-parse', '--show-toplevel'], 
                              capture_output=True, text=True)
        repo_path = Path(result.stdout.strip())
        repo_name = repo_path.name
        print(f"\n💡 Your current repository name appears to be: {repo_name}")
        print(f"💡 Suggested command: git remote add bitbucket git@bitbucket.org:YOUR_USERNAME/{repo_name}.git")
    except Exception:
        pass

def test_git_operations():
    """Test Git operations with Bitbucket"""
    print_step(5, "Test Git Operations")
    
    print("🔧 Once remote is added, test these commands:")
    print("   git fetch bitbucket")
    print("   git push -u bitbucket main")
    print("   git pull bitbucket main")

def main():
    """Main setup function"""
    print("🚀 BITBUCKET GIT SETUP WIZARD")
    print("="*60)
    print("This will help you connect Git to your Bitbucket account")
    print("You mentioned you can login via UI, so let's set up Git access!")
    
    # Step 1: Get SSH key
    ssh_key = check_ssh_key()
    if not ssh_key:
        print("❌ Cannot proceed without SSH key")
        return
    
    # Step 2: Guide Bitbucket setup
    guide_bitbucket_setup()
    
    # Step 3: Test SSH connection
    print("\n" + "="*60)
    print("🎯 AFTER you've added the SSH key to Bitbucket, let's test it...")
    input("\nPress Enter after you've added the SSH key to Bitbucket...")
    
    if test_ssh_connection():
        print("\n🎉 SSH connection working!")
        setup_bitbucket_remote()
        test_git_operations()
        
        print_step(6, "Setup Complete!", "You can now use Git with Bitbucket")
        print("✅ SSH key configured")
        print("✅ Bitbucket connection tested")
        print("✅ Ready to add remote and push/pull")
        
        print("\n🚀 Next Steps:")
        print("1. Add Bitbucket remote to your repository")
        print("2. Push your code to Bitbucket")
        print("3. Enjoy seamless Git operations with Bitbucket!")
        
    else:
        print("\n❌ SSH connection failed")
        print("📝 Please check:")
        print("   1. SSH key was added correctly to Bitbucket")
        print("   2. You're using the correct SSH key")
        print("   3. No firewall blocking the connection")
        print("   4. Try running the test again after fixing")

if __name__ == "__main__":
    main()
