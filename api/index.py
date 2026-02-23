from flask import Flask, jsonify, request
from flask_caching import Cache
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import json
from colorama import Fore, Style, init
import warnings
from urllib3.exceptions import InsecureRequestWarning
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import base64
import os
import sys

# Add the current directory to path for protobuf imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import protobuf modules
try:
    import my_pb2
    import output_pb2
except ImportError:
    # Create placeholder classes if protobuf files are missing
    class my_pb2:
        class GameData:
            def __init__(self):
                self.timestamp = ""
                self.game_name = ""
                self.game_version = 0
                self.version_code = ""
                self.os_info = ""
                self.device_type = ""
                self.network_provider = ""
                self.connection_type = ""
                self.screen_width = 0
                self.screen_height = 0
                self.dpi = ""
                self.cpu_info = ""
                self.total_ram = 0
                self.gpu_name = ""
                self.gpu_version = ""
                self.user_id = ""
                self.ip_address = ""
                self.language = ""
                self.open_id = ""
                self.access_token = ""
                self.platform_type = 0
                self.device_form_factor = ""
                self.device_model = ""
                self.field_60 = 0
                self.field_61 = 0
                self.field_62 = 0
                self.field_63 = 0
                self.field_64 = 0
                self.field_65 = 0
                self.field_66 = 0
                self.field_67 = 0
                self.field_70 = 0
                self.field_73 = 0
                self.library_path = ""
                self.field_76 = 0
                self.apk_info = ""
                self.field_78 = 0
                self.field_79 = 0
                self.os_architecture = ""
                self.build_number = ""
                self.field_85 = 0
                self.graphics_backend = ""
                self.max_texture_units = 0
                self.rendering_api = 0
                self.encoded_field_89 = ""
                self.field_92 = 0
                self.marketplace = ""
                self.encryption_key = ""
                self.total_storage = 0
                self.field_97 = 0
                self.field_98 = 0
                self.field_99 = ""
                self.field_100 = b""
            
            def SerializeToString(self):
                return b"serialized_data_placeholder"

    class output_pb2:
        class Lokesh:
            def ParseFromString(self, data):
                pass
            
            def __str__(self):
                return "region: IN\nstatus: success\ntoken: sample_token_123"

# تجاهل تحذيرات SSL
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# مفاتيح التشفير
AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV = b'6oyZDr22E3ychjM%'

# تهيئة colorama (مع تعطيل لـ Vercel)
init(autoreset=True, strip=True)

# تهيئة تطبيق Flask
app = Flask(__name__)

# تهيئة التخزين المؤقت (معدل لـ Vercel)
app.config['CACHE_TYPE'] = 'simple'  # Simple in-memory cache for Vercel
cache = Cache(app)


def get_token(password, uid):
    """Get access token using password and UID"""
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    headers = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "GarenaMSDK/4.0.19P4 (Vivo Y15c; Android 12; en;IN;)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close"
    }
    data = {
        "uid": uid,
        "password": password,
        "response_type": "token",
        "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067"
    }
    try:
        response = requests.post(url, headers=headers, data=data, verify=False, timeout=10)
        if response.status_code != 200:
            print(Fore.RED + f"Failed to retrieve token for UID {uid}: {response.text}")
            return None
        return response.json()
    except Exception as e:
        print(Fore.RED + f"Error getting token: {e}")
        return None


def get_token_inspect_data(access_token):
    """Inspect access token to get open_id and platform info"""
    try:
        url = f"https://100067.connect.garena.com/oauth/token/inspect?token={access_token}"
        headers = {
            "User-Agent": "GarenaMSDK/4.0.19P4 (Vivo Y15c; Android 12; en;IN;)",
            "Connection": "close"
        }
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'open_id' in data and 'platform' in data and 'uid' in data:
                return data
    except Exception as e:
        print(Fore.RED + f"Error inspecting token: {e}")
    return None


def encrypt_message(key, iv, plaintext):
    """Encrypt message using AES CBC"""
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_message = pad(plaintext, AES.block_size)
    encrypted_message = cipher.encrypt(padded_message)
    return encrypted_message


def load_tokens(file_path, limit=None):
    """Load tokens from file"""
    try:
        # For Vercel, we'll use a static path
        full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_path)
        with open(full_path, 'r') as file:
            data = json.load(file)
            tokens = list(data.items())
            if limit is not None:
                tokens = tokens[:limit]
            return tokens
    except Exception as e:
        print(Fore.RED + f"Failed to load tokens: {e}")
        # Return some test data if file doesn't exist
        return [("test_uid_1", "test_password_1"), ("test_uid_2", "test_password_2")][:limit] if limit else []


def parse_response(response_content):
    """Parse response to extract key fields"""
    response_dict = {}
    lines = response_content.split("\n")
    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            response_dict[key.strip()] = value.strip().strip('"')
    return response_dict


def process_token(uid, password):
    """Process token for UID/password combination"""
    token_data = get_token(password, uid)
    if not token_data:
        return {"uid": uid, "error": "Failed to retrieve token"}

    # إنشاء GameData Protobuf
    game_data = my_pb2.GameData()
    game_data.timestamp = "2025-05-29 13:11:47"
    game_data.game_name = "free fire"
    game_data.game_version = 1
    game_data.version_code = "1.118.1"
    game_data.os_info = "Android OS 11 / API-30 (RKQ1.201112.002/eng.realme.20221110.193122)"
    game_data.device_type = "Handheld"
    game_data.network_provider = "JIO"
    game_data.connection_type = "MOBILE"
    game_data.screen_width = 720
    game_data.screen_height = 1600
    game_data.dpi = "280"
    game_data.cpu_info = "ARM Cortex-A73 | 2200 | 4"
    game_data.total_ram = 4096
    game_data.gpu_name = "Adreno (TM) 610"
    game_data.gpu_version = "OpenGL ES 3.2"
    game_data.user_id = "Google|c71ff1e2-457f-4e2d-83a1-c519fa3f2a44"
    game_data.ip_address = "182.75.115.22"
    game_data.language = "en"
    game_data.open_id = token_data.get("open_id", "")
    game_data.access_token = token_data.get("access_token", "")
    game_data.platform_type = 4
    game_data.device_form_factor = "Handheld"
    game_data.device_model = "realme RMX1825"
    game_data.field_60 = 30000
    game_data.field_61 = 27500
    game_data.field_62 = 1940
    game_data.field_63 = 720
    game_data.field_64 = 28000
    game_data.field_65 = 30000
    game_data.field_66 = 28000
    game_data.field_67 = 30000
    game_data.field_70 = 4
    game_data.field_73 = 2
    game_data.library_path = "/data/app/com.dts.freefireth-XaT5M7jRwEL-nPaKOQvqdg==/lib/arm"
    game_data.field_76 = 1
    game_data.apk_info = "2f4a7f349f3a3ea581fc4d803bc5a977|/data/app/com.dts.freefireth-XaT5M7jRwEL-nPaKOQvqdg==/base.apk"
    game_data.field_78 = 6
    game_data.field_79 = 1
    game_data.os_architecture = "64"
    game_data.build_number = "2022041388"
    game_data.field_85 = 1
    game_data.graphics_backend = "OpenGLES3"
    game_data.max_texture_units = 16383
    game_data.rendering_api = 4
    game_data.encoded_field_89 = "\x10U\x15\x03\x02\t\rPYN\tEX\x03AZO9X\x07\rU\niZPVj\x05\rm\t\x04c"
    game_data.field_92 = 8999
    game_data.marketplace = "3rd_party"
    game_data.encryption_key = "Jp2DT7F3Is55K/92LSJ4PWkJxZnMzSNn+HEBK2AFBDBdrLpWTA3bZjtbU3JbXigkIFFJ5ZJKi0fpnlJCPDD2A7h2aPQ="
    game_data.total_storage = 64000
    game_data.field_97 = 1
    game_data.field_98 = 1
    game_data.field_99 = "4"
    game_data.field_100 = b"4"

    # تسلسل البيانات
    serialized_data = game_data.SerializeToString()

    # تشفير البيانات
    encrypted_data = encrypt_message(AES_KEY, AES_IV, serialized_data)
    hex_encrypted_data = binascii.hexlify(encrypted_data).decode('utf-8')

    # إرسال البيانات المشفرة إلى الخادم
    url = "https://loginbp.ggblueshark.com/MajorLogin"
    headers = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; ASUS_Z01QD Build/PI)",
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Content-Type': "application/octet-stream",
        'X-Unity-Version': "2018.4.11f1",
        'X-GA': "v1 1",
        'ReleaseVersion': "OB52"
    }
    edata = bytes.fromhex(hex_encrypted_data)

    try:
        response = requests.post(url, data=edata, headers=headers, verify=False, timeout=10)
        if response.status_code == 200:
            # محاولة فك تشفير الـ Protobuf
            example_msg = output_pb2.Lokesh()
            try:
                example_msg.ParseFromString(response.content)
                response_dict = parse_response(str(example_msg))
                
                return {
                    "region": response_dict.get("region", "N/A"),
                    "status": response_dict.get("status", "N/A"),
                    "team": "DURANTO",
                    "token": response_dict.get("token", "N/A"),
                    "token_access": game_data.access_token,
                    "uid": uid,
                }
            except Exception as e:
                return {
                    "uid": uid,
                    "error": f"Failed to deserialize the response: {e}",
                    "raw_response": response.text[:200]  # Limit raw response
                }
        else:
            return {
                "uid": uid,
                "error": f"Failed to get response: HTTP {response.status_code}"
            }
    except requests.RequestException as e:
        return {
            "uid": uid,
            "error": f"An error occurred while making the request: {e}"
        }


def process_access_token(access_token, uid=None, platform_type=4):
    """Process JWT generation using existing access token"""
    token_data = get_token_inspect_data(access_token)
    if not token_data:
        return {"success": False, "error": "INVALID_TOKEN", "message": "AccessToken invalid."}

    open_id = token_data.get("open_id", "")
    platform_type = token_data.get("platform", platform_type)
    uid = uid or str(token_data.get("uid", ""))

    # إنشاء GameData Protobuf مع access token المقدم
    game_data = my_pb2.GameData()
    game_data.timestamp = "2025-05-29 13:11:47"
    game_data.game_name = "free fire"
    game_data.game_version = 1
    game_data.version_code = "1.118.1"
    game_data.os_info = "Android OS 11 / API-30 (RKQ1.201112.002/eng.realme.20221110.193122)"
    game_data.device_type = "Handheld"
    game_data.network_provider = "JIO"
    game_data.connection_type = "MOBILE"
    game_data.screen_width = 720
    game_data.screen_height = 1600
    game_data.dpi = "280"
    game_data.cpu_info = "ARM Cortex-A73 | 2200 | 4"
    game_data.total_ram = 4096
    game_data.gpu_name = "Adreno (TM) 610"
    game_data.gpu_version = "OpenGL ES 3.2"
    game_data.user_id = uid
    game_data.ip_address = "182.75.115.22"
    game_data.language = "en"
    game_data.open_id = open_id
    game_data.access_token = access_token
    game_data.platform_type = platform_type
    game_data.device_form_factor = "Handheld"
    game_data.device_model = "realme RMX1825"
    game_data.field_60 = 30000
    game_data.field_61 = 27500
    game_data.field_62 = 1940
    game_data.field_63 = 720
    game_data.field_64 = 28000
    game_data.field_65 = 30000
    game_data.field_66 = 28000
    game_data.field_67 = 30000
    game_data.field_70 = 4
    game_data.field_73 = 2
    game_data.library_path = "/data/app/com.dts.freefireth-XaT5M7jRwEL-nPaKOQvqdg==/lib/arm"
    game_data.field_76 = 1
    game_data.apk_info = "2f4a7f349f3a3ea581fc4d803bc5a977|/data/app/com.dts.freefireth-XaT5M7jRwEL-nPaKOQvqdg==/base.apk"
    game_data.field_78 = 6
    game_data.field_79 = 1
    game_data.os_architecture = "64"
    game_data.build_number = "2022041388"
    game_data.field_85 = 1
    game_data.graphics_backend = "OpenGLES3"
    game_data.max_texture_units = 16383
    game_data.rendering_api = 4
    game_data.encoded_field_89 = "\x10U\x15\x03\x02\t\rPYN\tEX\x03AZO9X\x07\rU\niZPVj\x05\rm\t\x04c"
    game_data.field_92 = 8999
    game_data.marketplace = "3rd_party"
    game_data.encryption_key = "Jp2DT7F3Is55K/92LSJ4PWkJxZnMzSNn+HEBK2AFBDBdrLpWTA3bZjtbU3JbXigkIFFJ5ZJKi0fpnlJCPDD2A7h2aPQ="
    game_data.total_storage = 64000
    game_data.field_97 = 1
    game_data.field_98 = 1
    game_data.field_99 = str(platform_type)
    game_data.field_100 = str(platform_type).encode()

    # تسلسل البيانات
    serialized_data = game_data.SerializeToString()

    # تشفير البيانات
    encrypted_data = encrypt_message(AES_KEY, AES_IV, serialized_data)
    hex_encrypted_data = binascii.hexlify(encrypted_data).decode('utf-8')

    # إرسال البيانات المشفرة إلى الخادم
    url = "https://loginbp.ggblueshark.com/MajorLogin"
    headers = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; ASUS_Z01QD Build/PI)",
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Content-Type': "application/octet-stream",
        'X-Unity-Version': "2018.4.11f1",
        'X-GA': "v1 1",
        'ReleaseVersion': "OB52"
    }
    edata = bytes.fromhex(hex_encrypted_data)

    try:
        response = requests.post(url, data=edata, headers=headers, verify=False, timeout=10)
        if response.status_code == 200:
            example_msg = output_pb2.Lokesh()
            try:
                example_msg.ParseFromString(response.content)
                response_dict = parse_response(str(example_msg))
                
                return {
                    "success": True,
                    "region": response_dict.get("region", "N/A"),
                    "status": response_dict.get("status", "N/A"),
                    "team": "SOUMIK",
                    "BearerAuth": response_dict.get("token", "N/A"),
                    "uid": uid,
                    "open_id": open_id,
                    "platform_type": platform_type
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to deserialize the response: {e}"
                }
        else:
            error_text = response.text.strip()
            if "BR_PLATFORM_INVALID_PLATFORM" in error_text:
                return {"success": False, "error": "INVALID_PLATFORM", "message": "this account is registered on another platform"}
            elif "BR_GOP_TOKEN_AUTH_FAILED" in error_text:
                return {"success": False, "error": "INVALID_TOKEN", "message": "AccessToken invalid."}
            elif "BR_PLATFORM_INVALID_OPENID" in error_text:
                return {"success": False, "error": "INVALID_OPENID", "message": "OpenID invalid."}
            else:
                return {
                    "success": False,
                    "error": f"Failed to get response: HTTP {response.status_code}"
                }
    except requests.RequestException as e:
        return {
            "success": False,
            "error": f"An error occurred while making the request: {e}"
        }


@app.route('/token', methods=['GET'])
def get_responses():
    """Main token endpoint"""
    access_token = request.args.get('access_token')
    if access_token:
        cache_key = f"access_token_{access_token}"
        cached_response = cache.get(cache_key)
        if cached_response:
            return jsonify(cached_response)
        
        response = process_access_token(access_token)
        cache.set(cache_key, response, timeout=25200)
        return jsonify(response)

    uid = request.args.get('uid')
    password = request.args.get('password')

    if uid and password:
        cache_key = f"token_{uid}_{password}"
        cached_response = cache.get(cache_key)
        if cached_response:
            return jsonify(cached_response)
        
        response = process_token(uid, password)
        cache.set(cache_key, response, timeout=25200)
        return jsonify(response)

    limit = request.args.get('limit', default=10, type=int)  # Reduced limit for Vercel
    tokens = load_tokens("accs.txt", limit)
    responses = []

    # Use smaller thread pool for Vercel
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_uid = {executor.submit(process_token, uid, password): uid for uid, password in tokens}
        for future in as_completed(future_to_uid):
            try:
                response = future.result()
                responses.append(response)
            except Exception as e:
                responses.append({"uid": future_to_uid[future], "error": str(e)})

    token_list = [item['token'] for item in responses if 'token' in item]
    return jsonify({"tokens": token_list})


@app.route('/api/get_jwt', methods=['GET'])
def get_jwt():
    """API endpoint compatible with the original app.py"""
    access_token = request.args.get('access_token')
    guest_uid = request.args.get('guest_uid')
    guest_password = request.args.get('guest_password')

    if access_token:
        response = process_access_token(access_token)
        if response.get('success'):
            return jsonify({"success": True, "BearerAuth": response['BearerAuth']})
        else:
            return jsonify(response), 400

    elif guest_uid and guest_password:
        response = process_token(guest_uid, guest_password)
        if 'token' in response:
            return jsonify({"success": True, "BearerAuth": response['token']})
        else:
            return jsonify({
                "success": False,
                "message": "unregistered or banned account.",
                "detail": response.get('error', 'jwt not found in response.')
            }), 500

    return jsonify({
        "success": False,
        "message": "missing access_token (or guest_uid + guest_password)"
    }), 400


@app.route('/', methods=['GET'])
def home():
    """Home endpoint"""
    return jsonify({
        "status": "online",
        "message": "Free Fire JWT Generator API",
        "endpoints": {
            "/token": "GET - Get tokens (use ?access_token= or ?uid=&password= or ?limit=)",
            "/api/get_jwt": "GET - Get JWT (use ?access_token= or ?guest_uid=&guest_password=)"
        }
    })


# For local development
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5031))
    app.run(host='0.0.0.0', port=port)