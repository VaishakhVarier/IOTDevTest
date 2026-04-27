import requests
import time
import re
import csv
import subprocess
from datetime import datetime

# =========================
# INPUT VALIDATION
# =========================
def is_valid_ip(ip):
    pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
    return re.match(pattern, ip) and all(0 <= int(p) <= 255 for p in ip.split("."))

def is_valid_mac(mac):
    return bool(re.match(r"^([0-9A-Fa-f]{2}[:\-]?){5}[0-9A-Fa-f]{2}$", mac))

def normalize_mac(mac):
    return re.sub(r"[:\-]", "", mac).upper()

# =========================
# USER INPUT
# =========================
while True:
    DEVICE_IP = input("Enter Device IP: ").strip()
    if is_valid_ip(DEVICE_IP):
        break
    print("❌ Invalid IP")

while True:
    raw_mac = input("Enter Device MAC: ").strip()
    if is_valid_mac(raw_mac):
        DEVICE_MAC = normalize_mac(raw_mac)
        break
    print("❌ Invalid MAC")

DEVICE_URL = f"http://{DEVICE_IP}/system"
PASSCODE_NEW = DEVICE_MAC
HEADERS = {"Content-Type": "application/json"}

# =========================
# REQUEST + LATENCY
# =========================
def send_request(payload, retries=5, wait=2):
    for _ in range(retries):
        try:
            start = time.time()
            r = requests.post(DEVICE_URL, json=payload, headers=HEADERS, timeout=5)
            latency = int((time.time() - start) * 1000)
            if r.status_code == 200:
                return r.json(), latency
        except Exception as e:
            print(f"⚠️ {e}")
        time.sleep(wait)
    return None, None

# =========================
# PRODUCT + VERIFY
# =========================
def get_product():
    return send_request({"passcode": PASSCODE_NEW, "command": "product"})

def verify_fields(expected):
    res, lat = get_product()
    if not res:
        return False, "No response", lat

    ok = True
    for k, v in expected.items():
        if str(res.get(k)) != str(v):
            ok = False

    return ok, str(res), lat

# =========================
# REBOOT DETECTION
# =========================
def wait_for_reboot(timeout=40):
    start = time.time()
    down = False
    down_time = None

    while time.time() - start < timeout:
        try:
            requests.post(DEVICE_URL, json={"command": "product"}, timeout=2)
            if down:
                return True, round(time.time() - down_time, 2)
        except:
            if not down:
                down = True
                down_time = time.time()
        time.sleep(1)

    return False, 0

def wait_product():
    for _ in range(15):
        res, _ = get_product()
        if res:
            return True, str(res)
        time.sleep(2)
    return False, "No response"

# =========================
# CORE FLOW
# =========================
def config_flow(payload, expected=None):
    _, config_lat = send_request(payload)

    rebooted, dt = wait_for_reboot()
    up, prod = wait_product()

    if expected:
        ok, obs, verify_lat = verify_fields(expected)
    else:
        ok, obs, verify_lat = True, prod, 0

    final = f"{obs} | reboot_dt={dt}s | config_lat={config_lat}ms | verify_lat={verify_lat}ms"

    return rebooted and up and ok, final

# =========================
# TEST FUNCTIONS
# =========================

def set_passcode():
    return config_flow({"passcode": PASSCODE_NEW, "command": "config", "setPasscode": PASSCODE_NEW})

def set_srid():
    return config_flow(
        {"passcode": PASSCODE_NEW, "command": "config", "systemSrid": "123456789ABC"},
        {"srID": "123456789ABC"}
    )

def configure_wifi():
    return config_flow(
        {"passcode": PASSCODE_NEW, "command": "config",
         "primarySsid": "e_b",
         "primaryPassword": "bench@rnd1234"}
    )

def configure_softap():
    return config_flow(
        {"passcode": PASSCODE_NEW, "command": "config",
         "softapSsid": f"BTWN_{DEVICE_MAC[-4:]}",
         "softapPassword": "123456789"}
    )

def set_server():
    return config_flow(
        {"passcode": PASSCODE_NEW, "command": "config", "serverType": "5"},
        {"serverType": "5"}
    )

def set_mqtt():
    return config_flow(
        {"passcode": PASSCODE_NEW, "command": "config",
         "serverType": "2",
         "mqttServerName": "rnd-ms.buildtrack.in",
         "mqttServerPort": "1899",
         "mqttUsername": "btmqtt",
         "mqttPassword": "btmqtt123",
         "mqttSsl": "1"}
    )

def configure_udp():
    return config_flow(
        {"passcode": PASSCODE_NEW, "command": "config",
         "udpIp": "239.0.1.5",
         "udpPort": "49152",
         "udpStatus": "1"}
    )

def set_boot_delay():
    return config_flow(
        {"passcode": PASSCODE_NEW, "command": "config", "bootDelay": "5"}
    )

def set_product_name():
    return config_flow(
        {"passcode": PASSCODE_NEW, "command": "config", "productName": "Test_Device"},
        {"productName": "Test_Device"}
    )

# MQTT ops (no reboot expected)
def subscribe_topic():
    res, lat = send_request({"passcode": PASSCODE_NEW, "command": "subscribe",
                             "topic": f"{DEVICE_MAC}/status", "qos": "1"})
    return res is not None, f"lat={lat}ms"

def unsubscribe_topic():
    res, lat = send_request({"passcode": PASSCODE_NEW, "command": "unsubscribe",
                             "topic": f"{DEVICE_MAC}/status"})
    return res is not None, f"lat={lat}ms"

def get_subs():
    res, lat = send_request({"passcode": PASSCODE_NEW, "command": "getSubsList"})
    return res is not None, f"lat={lat}ms"

def set_will():
    res, lat = send_request({"passcode": PASSCODE_NEW, "command": "setWill"})
    return res is not None, f"lat={lat}ms"

def get_will():
    res, lat = send_request({"passcode": PASSCODE_NEW, "command": "getWill"})
    return res is not None, f"lat={lat}ms"

def configure_ping():
    ok, obs = config_flow(
        {"passcode": PASSCODE_NEW, "command": "config",
         "pingIPAddr1": DEVICE_IP,
         "pingIPAddr2": "8.8.8.8"}
    )
    return ok, obs

def reboot():
    _, lat = send_request({"passcode": PASSCODE_NEW, "command": "reboot"})
    rebooted, dt = wait_for_reboot()
    up, obs = wait_product()
    return rebooted and up, f"{obs} | reboot_dt={dt}s | cmd_lat={lat}ms"

# =========================
# RUNNER
# =========================
def run_test(name, func):
    print(f"\n▶ {name}")
    start = time.time()

    try:
        success, obs = func()
    except Exception as e:
        success, obs = False, str(e)

    total = round(time.time() - start, 2)
    status = "PASS" if success else "FAIL"

    print(f"{status} ({total}s)")
    print(obs)

    return {
        "test_name": name,
        "observed": obs,
        "status": status,
        "time": total
    }

# =========================
# MAIN
# =========================
def run_all():
    tests = [
        ("Passcode", set_passcode),
        ("SRID", set_srid),
        ("WiFi", configure_wifi),
        ("SoftAP", configure_softap),
        ("Server", set_server),
        ("MQTT", set_mqtt),
        ("UDP", configure_udp),
        ("BootDelay", set_boot_delay),
        ("ProductName", set_product_name),
        ("Subscribe", subscribe_topic),
        ("GetSubs", get_subs),
        ("Unsubscribe", unsubscribe_topic),
        ("SetWill", set_will),
        ("GetWill", get_will),
        ("Ping", configure_ping),
        ("Reboot", reboot),
    ]

    results = []

    for name, func in tests:
        results.append(run_test(name, func))

    print("\n==== SUMMARY ====")
    for r in results:
        print(f"{r['test_name']}: {r['status']}")

if __name__ == "__main__":
    run_all()