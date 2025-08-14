import subprocess
import time

for i in range(2):
    print(f"Run {i+1}...")
    subprocess.run(["python", "translatorV3.py"], check=True)
    time.sleep(3)  # wait 3 seconds before next run
