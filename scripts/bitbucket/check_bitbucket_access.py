#!/usr/bin/env python3
"""
Check Bitbucket Access and Configuration
"""
import os
import subprocess
import json
from pathlib import Path

def check_git_remotes():
    """Check git remotes for Bitbucket URLs"""
    print("🔍 Checking Git Remotes...")
    
    try:
        result = subprocess.run(['git', 'remote', '-v'], 
                              capture_output=True, text=True, cwd='.')
        remotes = result.stdout.strip().split('\n')
        
        bitbucket_found = False
        github_found = False
        
        for remote in remotes:
            if 'bitbucket' in remote.lower():
                print(f"✅ Bitbucket Remote Found: {remote}")
                bitbucket_found = True
            elif 'github' in remote.lower():
                print(f"📦 GitHub Remote Found: {remote}")
                github_found = True
        
        if not bitbucket_found:
            print("❌ No Bitbucket remotes found")
        
        return bitbucket_found, github_found
        
    except Exception as e:
        print(f"❌ Error checking remotes: {e}")
        return False, False

def check_git_config():
    """Check git configuration for Bitbucket"""
    print("\n⚙️ Checking Git Configuration...")
    
    try:
        # Check global config
        result = subprocess.run(['git', 'config', '--global', '--list'], 
                              capture_output=True, text=True)
        global_config = result.stdout
        
        # Check local config
        result = subprocess.run(['git', 'config', '--local', '--list'], 
                              capture_output=True, text=True)
        local_config = result.stdout
        
        configs = global_config + '\n' + local_config
        
        bitbucket_configs = []
        for line in configs.split('\n'):
            if 'bitbucket' in line.lower():
                bitbucket_configs.append(line)
        
        if bitbucket_configs:
            print("✅ Bitbucket Configuration Found:")
            for config in bitbucket_configs:
                print(f"   {config}")
        else:
            print("❌ No Bitbucket configuration found")
        
        return len(bitbucket_configs) > 0
        
    except Exception as e:
        print(f"❌ Error checking config: {e}")
        return False

def check_ssh_keys():
    """Check for SSH keys that might be used for Bitbucket"""
    print("\n🔑 Checking SSH Keys...")
    
    ssh_dir = Path.home() / '.ssh'
    if ssh_dir.exists():
        key_files = list(ssh_dir.glob('id_*'))
        
        if key_files:
            print(f"✅ Found {len(key_files)} SSH key files:")
            for key_file in key_files:
                print(f"   {key_file.name}")
            
            # Check if any keys are loaded in ssh-agent
            try:
                result = subprocess.run(['ssh-add', '-l'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    keys = result.stdout.strip().split('\n')
                    print(f"✅ {len(keys)} SSH keys loaded in agent:")
                    for key in keys:
                        print(f"   {key}")
                else:
                    print("ℹ️ No SSH keys loaded in agent")
            except Exception:
                print("ℹ️ Could not check ssh-agent")
        else:
            print("❌ No SSH keys found")
    else:
        print("❌ .ssh directory not found")

def check_bitbucket_connectivity():
    """Test connectivity to Bitbucket"""
    print("\n🌐 Testing Bitbucket Connectivity...")
    
    # Test HTTPS connectivity
    try:
        result = subprocess.run(['git', 'ls-remote', 'https://bitbucket.org'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ HTTPS connectivity to Bitbucket successful")
            return True
        else:
            print(f"❌ HTTPS connectivity failed: {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ HTTPS connectivity timeout")
        return False
    except Exception as e:
        print(f"❌ HTTPS connectivity error: {e}")
        return False

def check_github_cli():
    """Check if GitHub CLI is available and configured"""
    print("\n📦 Checking GitHub CLI...")
    
    try:
        result = subprocess.run(['gh', 'auth', 'status'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ GitHub CLI authenticated")
            print(f"   {result.stdout.strip()}")
            return True
        else:
            print("❌ GitHub CLI not authenticated")
            return False
    except FileNotFoundError:
        print("❌ GitHub CLI not installed")
        return False
    except Exception as e:
        print(f"❌ GitHub CLI error: {e}")
        return False

def check_environment_variables():
    """Check environment variables for Bitbucket"""
    print("\n🌍 Checking Environment Variables...")
    
    bitbucket_vars = []
    for key, value in os.environ.items():
        if 'bitbucket' in key.lower():
            bitbucket_vars.append((key, value))
    
    if bitbucket_vars:
        print("✅ Bitbucket environment variables found:")
        for key, value in bitbucket_vars:
            print(f"   {key}={'*' * len(value)}")
    else:
        print("ℹ️ No Bitbucket environment variables found")
    
    return len(bitbucket_vars) > 0

def main():
    """Main function to check Bitbucket access"""
    print("🔍 BITBUCKET ACCESS CHECK")
    print("="*50)
    
    # Run all checks
    has_bitbucket_remote, has_github_remote = check_git_remotes()
    has_bitbucket_config = check_git_config()
    check_ssh_keys()
    has_bitbucket_connectivity = check_bitbucket_connectivity()
    has_github_cli = check_github_cli()
    has_bitbucket_env = check_environment_variables()
    
    # Summary
    print("\n" + "="*50)
    print("📊 ACCESS SUMMARY")
    print("="*50)
    
    print(f"Bitbucket Remote:     {'✅' if has_bitbucket_remote else '❌'}")
    print(f"Bitbucket Config:     {'✅' if has_bitbucket_config else '❌'}")
    print(f"Bitbucket Connectivity: {'✅' if has_bitbucket_connectivity else '❌'}")
    print(f"Bitbucket Environment: {'✅' if has_bitbucket_env else '❌'}")
    print(f"GitHub Remote:         {'✅' if has_github_remote else '❌'}")
    print(f"GitHub CLI:            {'✅' if has_github_cli else '❌'}")
    
    # Recommendations
    print("\n🎯 RECOMMENDATIONS")
    print("="*50)
    
    if not has_bitbucket_remote and not has_bitbucket_config:
        print("❌ No Bitbucket configuration found")
        print("📝 To add Bitbucket access:")
        print("   1. Create SSH key: ssh-keygen -t ed25519 -C 'your-email@example.com'")
        print("   2. Add SSH key to Bitbucket account")
        print("   3. Add remote: git remote add bitbucket git@bitbucket.org:username/repo.git")
    
    elif has_bitbucket_remote and not has_bitbucket_connectivity:
        print("⚠️ Bitbucket remote found but no connectivity")
        print("📝 Check:")
        print("   1. SSH key is added to Bitbucket account")
        print("   2. SSH key is loaded in ssh-agent")
        print("   3. Network connectivity to Bitbucket")
    
    elif has_bitbucket_connectivity:
        print("✅ Bitbucket access is working!")
        print("🚀 You can push/pull from Bitbucket repositories")
    
    if has_github_cli:
        print("✅ GitHub CLI is available for GitHub operations")
    
    if has_github_remote:
        print("📦 GitHub remotes are configured")

if __name__ == "__main__":
    main()
