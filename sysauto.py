import requests
import time
import subprocess
import re

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

# =========================
# CONFIG
# =========================
PASSCODE_NEW = DEVICE_MAC
HEADERS = {"Content-Type": "application/json"}

# =========================
# REQUEST
# =========================
def send_request(payload, retries=5, wait=2):
    for _ in range(retries):
        try:
            r = requests.post(DEVICE_URL, json=payload, headers=HEADERS, timeout=5)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(wait)
    return None

# =========================
# DEVICE CHECK
# =========================
def is_device_alive():
    res = send_request({
        "passcode": PASSCODE_NEW,
        "command": "product"
    }, retries=2)
    return res is not None

# =========================
# VERIFY
# =========================
def verify_via_product(expected):
    res = send_request({"passcode": PASSCODE_NEW, "command": "product"})
    if not res:
        return False

    ok = True
    for k, v in expected.items():
        actual = str(res.get(k)).strip()
        if str(v).strip() != actual:
            print(f"  ❌ {k}: {actual} (expected {v})")
            ok = False
        else:
            print(f"  ✅ {k}: {actual}")
    return ok

# =========================
# PING
# =========================
def wait_for_ping(ip, duration=10):
    print(f"  [PING] Testing {ip}")
    start = time.time()
    while time.time() - start < duration:
        r = subprocess.run(["ping", "-c", "1", ip], capture_output=True)
        if r.returncode == 0:
            print(f"  ✅ Ping success: {ip}")
            return True
        time.sleep(1)
    print(f"  ❌ Ping failed: {ip}")
    return False

# =========================
# TEST FUNCTIONS
# =========================
def set_passcode():
    return send_request({
        "passcode": PASSCODE_NEW,
        "command": "config",
        "setPasscode": PASSCODE_NEW
    }) is not None

def set_srid():
    res = send_request({
        "passcode": PASSCODE_NEW,
        "command": "config",
        "systemSrid": "123456789ABC"
    })
    return res and verify_via_product({"srID": "123456789ABC"})

def configure_wifi():
    res = send_request({
        "passcode": PASSCODE_NEW,
        "command": "config",
        "primarySsid": "Hardware Team",
        "primaryPassword": "BuildTrack50"
    })
    time.sleep(3)
    return res is not None

def configure_softap():
    return send_request({
        "passcode": PASSCODE_NEW,
        "command": "config",
        "softapSsid": f"BTWN_{DEVICE_MAC[-4:]}",
        "softapPassword": "123456789"
    }) is not None

def set_server():
    res = send_request({
        "passcode": PASSCODE_NEW,
        "command": "config",
        "serverType": "5"
    })
    return res and verify_via_product({"serverType": "5"})

# ✅ FIXED MQTT
def set_mqtt():
    payload = {
        "passcode": PASSCODE_NEW,
        "command": "config",
        "serverType": "2",
        "mqttServerName": "rnd-ms.buildtrack.in",
        "mqttServerPort": "1899",
        "mqttUsername": "btmqtt",
        "mqttPassword": "btmqtt123",
        "mqttSsl": "1",
        "setAuthPath": "https://rnd-ms.buildtrack.in/service/ota/v1/getFP/1/"
    }

    res = send_request(payload)

    if not res:
        print("  ❌ No response from device")
        return False

    print("  [MQTT] Waiting for provisioning...")

    # 🔁 Poll instead of fixed sleep
    for _ in range(10):
        prod = send_request({
            "passcode": PASSCODE_NEW,
            "command": "product"
        })

        if prod:
            # Check mode
            if prod.get("serverType") == "2":
                
                mqtt_path = prod.get("mqttServerPath", [])
                mqtt_state = prod.get("mqttState", [])

                if (
                    len(mqtt_path) >= 2 and
                    mqtt_path[0] == "rnd-ms.buildtrack.in" and
                    mqtt_path[1] == "1899" and
                    mqtt_state == ["1", "1"]
                ):
                    print("  ✅ MQTT Connected")
                    return True

        print("  ⏳ Waiting MQTT connection...")
        time.sleep(3)

    print("  ❌ MQTT not connected")
    return False

# MQTT ops
def subscribe_topic():
    return send_request({
        "passcode": PASSCODE_NEW,
        "command": "subscribe",
        "topic": f"{DEVICE_MAC}/status",
        "qos": "1"
    }) is not None

def get_subs():
    return send_request({
        "passcode": PASSCODE_NEW,
        "command": "getSubsList"
    }) is not None

def unsubscribe_topic():
    return send_request({
        "passcode": PASSCODE_NEW,
        "command": "unsubscribe",
        "topic": f"{DEVICE_MAC}/status"
    }) is not None

def set_will():
    return send_request({
        "passcode": PASSCODE_NEW,
        "command": "setWill",
        "status": "1",
        "topic": "test/lwt",
        "payload": "byebye",
        "qos": "1",
        "retain": "1"
    }) is not None

def get_will():
    return send_request({
        "passcode": PASSCODE_NEW,
        "command": "getWill"
    }) is not None

def set_mqtt_alive():
    return send_request({
        "passcode": PASSCODE_NEW,
        "command": "config",
        "mqttSetAlive": "60"
    }) is not None

def configure_udp():
    return send_request({
        "passcode": PASSCODE_NEW,
        "command": "config",
        "udpIp": "239.0.1.5",
        "udpPort": "49152",
        "udpStatus": "1"
    }) is not None

def set_boot_delay():
    return send_request({
        "passcode": PASSCODE_NEW,
        "command": "config",
        "bootDelay": "5"
    }) is not None

def set_product_name():
    return send_request({
        "passcode": PASSCODE_NEW,
        "command": "config",
        "productName": "Test_Device"
    }) is not None

def configure_ping():
    res = send_request({
        "passcode": PASSCODE_NEW,
        "command": "config",
        "pingIPAddr1": DEVICE_IP,   # 👈 changed
        "pingIPAddr2": "8.8.8.8"
    })

    if not res:
        print("  ❌ Ping config failed")
        return False

    print("  [PING] Checking device reachability...")
    time.sleep(3)

    if wait_for_ping(DEVICE_IP):
        print("  ✅ Device reachable")
        return True

    print("  ❌ Device not reachable")
    return False

def reboot():
    send_request({
        "passcode": PASSCODE_NEW,
        "command": "reboot"
    })
    time.sleep(10)
    return is_device_alive()

# =========================
# RUNNER
# =========================
def run_test(name, func):
    print(f"\n▶ {name}")
    start = time.time()

    try:
        result = func()
    except Exception as e:
        print(f"  ❌ Exception: {e}")
        result = False

    status = "PASS" if result else "FAIL"
    print(f"{status} ({round(time.time() - start, 2)}s)")
    return {"test_name": name, "status": status}

def run_all():
    tests = [
        ("Passcode", set_passcode),
        ("SRID", set_srid),
        ("WiFi", configure_wifi),
        ("SoftAP", configure_softap),
        ("Server", set_server),
        ("MQTT Config", set_mqtt),

        ("Subscribe", subscribe_topic),
        ("Get Subs", get_subs),
        ("Unsubscribe", unsubscribe_topic),

        ("Set Will", set_will),
        ("Get Will", get_will),

        ("MQTT Alive", set_mqtt_alive),
        ("UDP", configure_udp),
        ("Boot Delay", set_boot_delay),
        ("Product Name", set_product_name),

        ("Ping", configure_ping),
        ("Reboot", reboot),
    ]

    results = []

    for name, func in tests:
        r = run_test(name, func)
        results.append(r)

    print("\n==== SUMMARY ====")
    for r in results:
        print(f"{r['test_name']}: {r['status']}")



# =========================
# MAIN
# =========================
if __name__ == "__main__":
    run_all()


