"""LLM client abstraction supporting Anthropic and OpenAI-compatible APIs."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import anthropic
import openai

from ..config import Settings, get_settings


@dataclass
class LLMResponse:
    """Response from LLM."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None, max_tokens: int = 4096) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            prompt: User prompt
            system: Optional system prompt
            max_tokens: Maximum tokens in response

        Returns:
            LLMResponse with generated content
        """
        pass


class AnthropicClient(LLMClient):
    """Anthropic Claude API client."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def generate(self, prompt: str, system: str | None = None, max_tokens: int = 4096) -> LLMResponse:
        """Generate using Anthropic API."""
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        response = await self.client.messages.create(**kwargs)

        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )


class OpenAICompatibleClient(LLMClient):
    """OpenAI-compatible API client (works with vLLM, local inference, etc.)."""

    def __init__(self, api_key: str, base_url: str | None = None, model: str = "gpt-4") -> None:
        self.client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def generate(self, prompt: str, system: str | None = None, max_tokens: int = 4096) -> LLMResponse:
        """Generate using OpenAI-compatible API."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    """Get configured LLM client based on settings.

    Args:
        settings: Optional settings, uses default if not provided

    Returns:
        Configured LLMClient instance

    Raises:
        ValueError: If LLM API key is not configured
    """
    if settings is None:
        settings = get_settings()

    if not settings.llm_api_key:
        raise ValueError("LLM API key not configured. Set LLM_API_KEY environment variable.")

    if settings.llm_provider == "anthropic":
        return AnthropicClient(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
    elif settings.llm_provider == "openai":
        return OpenAICompatibleClient(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
