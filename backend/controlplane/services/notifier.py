"""역할 기반 이메일 알림 (decision-email-alerting).

라우팅: 인증 해지(401) -> admin · 과제 실패 -> 담당자+admin · 소스 자동 비활성화 -> admin.
notify_mode=log 이면 발송 대신 구조화 로그만 남긴다 (개발/스테이징).
"""
from __future__ import annotations

from email.mime.text import MIMEText
import logging
import smtplib

from ..settings import ControlPlaneSettings

log = logging.getLogger("controlplane.notifier")


class Notifier:
    def __init__(self, settings: ControlPlaneSettings):
        self.settings = settings

    def _recipients(self, to: list[str]) -> list[str]:
        seen = []
        for addr in to:
            addr = (addr or "").strip()
            if addr and addr not in seen:
                seen.append(addr)
        return seen

    def send(self, *, subject: str, body: str, to: list[str]) -> bool:
        to = self._recipients(to)
        if not to:
            log.warning("알림 수신자 없음 — 건너뜀: %s", subject)
            return False
        if self.settings.notify_mode != "smtp":
            log.info("[notify:log] to=%s subject=%s\n%s", to, subject, body)
            return True
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = self.settings.smtp_from
            msg["To"] = ", ".join(to)
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as s:
                if self.settings.smtp_starttls:
                    s.starttls()
                if self.settings.smtp_user:
                    s.login(self.settings.smtp_user, self.settings.smtp_password)
                s.sendmail(self.settings.smtp_from, to, msg.as_string())
            return True
        except Exception as e:  # noqa: BLE001 — 알림 실패가 파이프라인을 죽이면 안 된다
            log.error("이메일 발송 실패: %s: %s", type(e).__name__, e)
            return False

    # ── 역할 기반 헬퍼 ──
    def run_failed(self, *, source_label: str, run_id: str, error: str,
                   owner_email: str = "") -> None:
        self.send(
            subject=f"[wiki-pipeline] 실행 실패 — {source_label} ({run_id})",
            body=f"source: {source_label}\nrun: {run_id}\n\n오류:\n{error}",
            to=[owner_email, self.settings.admin_email],
        )

    def auth_revoked(self, *, where: str, detail: str) -> None:
        self.send(
            subject=f"[wiki-pipeline] 인증 실패(401/403) — {where}",
            body=f"{where} 인증이 거부되었습니다. 토큰을 갱신하세요.\n\n{detail}",
            to=[self.settings.admin_email],
        )

    def source_disabled(self, *, source_label: str, reason: str) -> None:
        self.send(
            subject=f"[wiki-pipeline] 소스 자동 비활성화 — {source_label}",
            body=(f"compare 404 등으로 소스가 자동 비활성화되었습니다 "
                  f"(decision-branch-loss-policy).\n\n사유: {reason}\n"
                  f"대시보드에서 브랜치를 다시 지정하면 재활성화됩니다."),
            to=[self.settings.admin_email],
        )

    def token_rotation_warning(self, *, stale_instance_ids: list[str],
                                threshold_days: int) -> None:
        """SCM 토큰 순환 경고 전용 — 예전에는 run_failed를 끌어다 써서
        subject가 "실행 실패"로 잘못 표시되는 버그가 있었다 (scheduler.py).
        토큰 순환은 admin-only — 담당자 모르는 시스템 이벤트.
        """
        if not stale_instance_ids:
            return
        preview = ", ".join(stale_instance_ids[:5])
        more = f" (+{len(stale_instance_ids) - 5}건)" if len(stale_instance_ids) > 5 else ""
        self.send(
            subject=f"[wiki-pipeline] SCM 토큰 순환 경고 — {len(stale_instance_ids)}개 인스턴스",
            body=(f"토큰 순환 기준일({threshold_days}일)을 넘긴 SCM 인스턴스:\n"
                  f"  {preview}{more}\n\n"
                  f"대시보드에서 토큰을 갱신하세요 (decision-cloud-scm-token-policy)."),
            to=[self.settings.admin_email],
        )
