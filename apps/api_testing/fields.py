"""透明加密 JSON 字段：落库为 AES 密文，读取自动解密为 Python dict/list"""
from django.db import models

from . import crypto


class EncryptedJSONField(models.TextField):
    description = '落库加密的 JSON 字段'

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('default', dict)
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        return crypto.decrypt_json(value)

    def to_python(self, value):
        return crypto.decrypt_json(value)

    def get_prep_value(self, value):
        return crypto.encrypt_json(value)
