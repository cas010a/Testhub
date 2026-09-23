"""接口测试入参落库加密工具

对 ApiRequest 的 body/params/headers 等 JSON 字段做 AES-256-CBC 加密，
密钥来自 settings.TEST_DATA_ENCRYPT_KEY（写入 .env，不进 git）。
密文带 `enc:v1:` 前缀，读取时能区分明文（历史数据）与密文。
"""
import base64
import json

from django.conf import settings

try:
    from Crypto.Cipher import AES
    from Crypto.Protocol.KDF import PBKDF2
    from Crypto.Util.Padding import pad, unpad
    from Crypto.Random import get_random_bytes
    CRYPTO_OK = True
except ImportError:  # pragma: no cover
    CRYPTO_OK = False

PREFIX = 'enc:v1:'
_SALT_LEN = 16
_IV_LEN = 16
_ITER = 100000


def get_encrypt_key():
    key = getattr(settings, 'TEST_DATA_ENCRYPT_KEY', '') or ''
    if not key:
        raise RuntimeError('缺少 TEST_DATA_ENCRYPT_KEY 配置，请在 .env 中设置')
    return key


def _derive_key(password, salt):
    return PBKDF2(password.encode('utf-8'), salt, dkLen=32, count=_ITER)


def encrypt_text(text):
    """加密字符串，返回 `enc:v1:<base64>`"""
    if not CRYPTO_OK:
        raise RuntimeError('pycryptodome 未安装，无法加密')
    password = get_encrypt_key()
    salt = get_random_bytes(_SALT_LEN)
    iv = get_random_bytes(_IV_LEN)
    cipher = AES.new(_derive_key(password, salt), AES.MODE_CBC, iv)
    ct = cipher.encrypt(pad(text.encode('utf-8'), AES.block_size))
    return PREFIX + base64.b64encode(salt + iv + ct).decode('utf-8')


def decrypt_text(encrypted):
    """解密 `enc:v1:<base64>` 字符串，返回明文"""
    if not CRYPTO_OK:
        raise RuntimeError('pycryptodome 未安装，无法解密')
    password = get_encrypt_key()
    raw = base64.b64decode(encrypted.encode('utf-8'))
    salt, iv, ct = raw[:_SALT_LEN], raw[_SALT_LEN:_SALT_LEN + _IV_LEN], raw[_SALT_LEN + _IV_LEN:]
    cipher = AES.new(_derive_key(password, salt), AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(ct), AES.block_size).decode('utf-8')


def is_encrypted(value):
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt_json(value):
    """把 dict/list 序列化并加密为密文字符串（已是密文则原样返回）"""
    if value is None:
        return None
    if is_encrypted(value):
        return value
    return encrypt_text(json.dumps(value, ensure_ascii=False))


def decrypt_json(value):
    """把密文/明文解析回 Python 对象（dict/list）"""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        if is_encrypted(value):
            try:
                return json.loads(decrypt_text(value[len(PREFIX):]))
            except Exception:
                return None
        try:
            # 历史明文 JSON 直通
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value
    return value
