import os
import json
import time
import shutil
import argparse
import subprocess
import signal
from datetime import datetime
import google.generativeai as genai


parser = argparse.ArgumentParser(description="AI Self-Healing Fixer Service")
parser.add_argument("--key", required=True, help="Your Gemini API Key")
args = parser.parse_args()


genai.configure(api_key=args.key)
model = genai.GenerativeModel('gemini-2.5-flash') 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PENDING_DIR = os.path.join(BASE_DIR, "pending_fixes")
FIXED_DIR = os.path.join(BASE_DIR, "fixed_logs")
TARGET_FILE = os.path.join(BASE_DIR, "server.py")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")


server_process = None

def start_server():
    """Starts server.py as a background process."""
    global server_process
    print(f"[*] Starting server: {TARGET_FILE}")
    
    server_process = subprocess.Popen(['python', TARGET_FILE])

def restart_server():
    """Kills the running server and starts it again."""
    global server_process
    if server_process:
        print("[*] Killing existing server process (PID: {})...".format(server_process.pid))
        server_process.terminate() 
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill() 
    
    start_server()

def get_gemini_fix(error_log, code_content):
    """Sends context to Gemini 2.5 and extracts the clean code."""
    prompt = f"""
    You are an automated self-healing CI/CD agent.
    
    ERROR DETECTED:
    {error_log}

    CURRENT SOURCE CODE:
    {code_content}

    TASK:
    1. Analyze the error and the source code.
    2. Provide a fix.
    3. Return ONLY the complete, corrected source code. Fix any error if it exists. if i manually cause an error fix that also
     
    4. DO NOT include markdown code blocks (```python). 
    5. DO NOT include any explanations or commentary.
    """
    
    response = model.generate_content(prompt)
    
    text = response.text.replace("```python", "").replace("```", "").strip()
    return text

def process_fix(json_file_path):
    try:
        with open(json_file_path, 'r') as f:
            data = json.load(f)
    except: return

    print(f"\n[!] Analyzing Error: {data['raw_log']}")
    
    with open(TARGET_FILE, 'r') as f:
        original_code = f.read()

    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(TARGET_FILE, os.path.join(BACKUP_DIR, f"backup_{ts}.py"))

    
    print("[*] Requesting fix from Gemini 2.5...")
    try:
        fixed_code = get_gemini_fix(data['raw_log'], original_code)

        if not fixed_code or len(fixed_code) < 10:
            print("[-] Invalid code returned. Skipping.")
            return

        
        with open(TARGET_FILE, 'w') as f:
            f.write(fixed_code)
        print("[+] Fix applied to file.")

        
        restart_server()

        
        data['status'] = 'fixed'
        data['fixed_at'] = datetime.now().isoformat()
        with open(json_file_path, 'w') as f:
            json.dump(data, f, indent=4)
        
        shutil.move(json_file_path, os.path.join(FIXED_DIR, os.path.basename(json_file_path)))
        print(f"[+] Server restarted and log archived.")
        
    except Exception as e:
        print(f"[-] AI Generation failed: {e}")

if __name__ == "__main__":
    for folder in [PENDING_DIR, FIXED_DIR, BACKUP_DIR]:
        os.makedirs(folder, exist_ok=True)

    print("--- Service B (Gemini Fixer & Manager) Started ---")
    
    
    start_server()

    while True:
        files = [f for f in os.listdir(PENDING_DIR) if f.endswith(".json")]
        for file in files:
            process_fix(os.path.join(PENDING_DIR, file))
        time.sleep(3)