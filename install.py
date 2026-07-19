import subprocess
import sys
import os

CORE_REQS = "requirements.txt"
OPTIONAL_PACKAGES = ["curl_cffi", "rookiepy", "reportlab", "python-docx"]

def run_install():
    print("  Focal Harvest Dependency Installer  \n")
    
    # 1. Install core requirements
    if os.path.exists(CORE_REQS):
        print(f"📦 Installing core dependencies from {CORE_REQS}...")
        result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", CORE_REQS])
        if result.returncode == 0:
            print("✅ Core dependencies installed successfully.\n")
        else:
            print("⚠️ Some core dependencies failed to install. Retrying individually...\n")
            # Fallback to individual install if bulk fails
            try_individual_install(CORE_REQS)
    else:
        print(f"❌ Error: {CORE_REQS} not found in current directory.")
        sys.exit(1)

    # 2. Attempt optional enhancements
    print("🚀 Attempting optional enhancements...")
    for pkg in OPTIONAL_PACKAGES:
        print(f"📦 Trying optional package: {pkg}")
        result = subprocess.run([sys.executable, "-m", "pip", "install", pkg])
        if result.returncode == 0:
            print(f"✅ Successfully installed optional package: {pkg}\n")
        else:
            print(f"⚠️ Skipped optional package (not supported on this system): {pkg}\n")

    print("🎉 Setup complete! Run Focal Harvest using: python main.py")

def try_individual_install(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                package = line.strip()
                if not package or package.startswith("#"):
                    continue
                print(f"📦 Installing: {package}")
                subprocess.run([sys.executable, "-m", "pip", "install", package])
    except Exception as e:
        print(f"Error reading file: {e}")

if __name__ == "__main__":
    run_install()
