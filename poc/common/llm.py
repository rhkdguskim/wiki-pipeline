"""공급자 중립 LLM 클라이언트 팩토리.

decision-model-provider-neutral-minimax: 공급자를 base_url·key·model로 갈아끼운다.
반환 타입은 항상 langchain BaseChatModel이라, 그래프·도구 바인딩 코드는 공급자를 모른다.

M3는 OpenAI 호환 엔드포인트를 쓴다 — langchain tool-calling이 OpenAI 스키마에서 가장
안정적이고, base_url 교체만으로 중립이 성립하기 때문.
"""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from .config import Settings


def build_chat_model(settings: Settings) -> BaseChatModel:
    provider = settings.llm_provider.lower()

    if provider in ("minimax", "openai", "openai-compatible"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=120,
            max_retries=0,  # 재시도는 common/retry.py가 관측과 함께 담당
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            base_url=settings.llm_base_url or None,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=120,
        )

    raise ValueError(f"알 수 없는 LLM_PROVIDER: {settings.llm_provider!r}")
