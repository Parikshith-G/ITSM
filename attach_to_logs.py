import time
import os
import json
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE_PATH = os.path.normpath(os.path.join(BASE_DIR, "logs", "app.log"))
ERROR_DIR = os.path.normpath(os.path.join(BASE_DIR, "pending_fixes"))
KEYWORDS = ["ERROR", "CRITICAL", "EXCEPTION", "TRACEBACK"]

class LogMonitorHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_position = 0

    def on_modified(self, event):
        if os.path.normpath(event.src_path) == LOG_FILE_PATH:
            self.process_logs()

    def process_logs(self):
        if not os.path.exists(LOG_FILE_PATH) or os.path.getsize(LOG_FILE_PATH) == 0:
            return

        
        found_error = False
        with open(LOG_FILE_PATH, 'r') as f:
            lines = f.readlines()
            for line in lines:
                if 'info' in line.lower():
                    continue
                if any(word in line.upper() for word in KEYWORDS):
                    print(f"!!! Match Found: {line.strip()}")
                    self.capture_error(line)
                    found_error = True

        
        
        try:
            with open(LOG_FILE_PATH, 'w') as f:
                f.write("") 
            print("[*] Logs processed and app.log cleared.")
            self.last_position = 0 
        except PermissionError:
            print("[-] Could not clear log file: It is currently locked by another process.")

    def capture_error(self, error_content):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"error_{timestamp}.json"
        filepath = os.path.join(ERROR_DIR, filename)
        
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "raw_log": error_content.strip(),
            "target_file": "server.py",
            "status": "pending_analysis"
        }

        with open(filepath, 'w') as f:
            json.dump(error_data, f, indent=4)
        print(f"[+] Saved error to: {filename}")

if __name__ == "__main__":
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    os.makedirs(ERROR_DIR, exist_ok=True)
    
    if not os.path.exists(LOG_FILE_PATH):
        with open(LOG_FILE_PATH, 'w') as f: pass

    event_handler = LogMonitorHandler()
    
    
    print("[*] Performing initial log scan and cleanup...")
    event_handler.process_logs()
    
    observer = Observer()
    log_folder = os.path.dirname(LOG_FILE_PATH)
    observer.schedule(event_handler, path=log_folder, recursive=False)
    
    print(f"--- Service A (Monitor & Cleaner) Started ---")
    print(f"Watching: {LOG_FILE_PATH}")
    
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()