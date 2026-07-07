"""시크릿 at-rest 암호화 — DB에 저장되는 토큰을 Fernet으로 감싼다.

question-secret-storage-security 해소: CONTROL_SECRET_KEY(Fernet key)가 설정되면
모든 토큰이 "enc:v1:<ciphertext>" 형태로 저장된다. 키가 없으면 평문 저장(개발 모드,
기동 시 경고). 접두사로 구분하므로 키 도입 후에도 기존 평문 레코드를 읽을 수 있고,
다음 저장 시점에 자동으로 암호화된다.

키 생성: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

_PREFIX = "enc:v1:"


class SecretBox:
    def __init__(self, key: str = ""):
        self._fernet = Fernet(key.encode()) if key.strip() else None

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    def encrypt(self, value: str) -> str:
        if not value or self._fernet is None:
            return value
        return _PREFIX + self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, stored: str) -> str:
        if not stored or not stored.startswith(_PREFIX):
            return stored   # 평문 레코드 (키 도입 전) — 그대로 반환
        if self._fernet is None:
            raise RuntimeError("암호화된 시크릿인데 CONTROL_SECRET_KEY가 없습니다.")
        try:
            return self._fernet.decrypt(stored[len(_PREFIX):].encode("ascii")).decode("utf-8")
        except InvalidToken as e:
            raise RuntimeError("시크릿 복호화 실패 — CONTROL_SECRET_KEY가 바뀌었습니까?") from e
