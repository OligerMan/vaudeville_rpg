"""LLM client abstraction supporting Anthropic and OpenAI-compatible APIs."""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import anthropic
import openai

from ..config import Settings, get_settings


def _setup_llm_logger(settings: Settings) -> logging.Logger:
    """Set up LLM interaction logger with file output and rotation.

    Args:
        settings: Application settings containing log directory and rotation config

    Returns:
        Configured logger instance
    """
    log_dir = Path(settings.llm_log_dir)
    log_dir.mkdir(exist_ok=True)

    # Rotate old logs - keep only last N sessions
    log_files = sorted(log_dir.glob("session_*.log"), key=lambda p: p.stat().st_mtime)
    if len(log_files) >= settings.llm_log_rotation_count:
        # Delete oldest files
        for old_file in log_files[: -(settings.llm_log_rotation_count - 1)]:
            old_file.unlink()

    # Create new log file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"session_{timestamp}.log"

    # Configure logger
    logger = logging.getLogger("llm_interactions")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()  # Clear any existing handlers

    # File handler
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(message)s")  # Simple format, we'll format manually
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


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
    async def generate(self, prompt: str, system: str | None = None, max_tokens: int = 2048) -> LLMResponse:
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

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514", settings: Settings | None = None) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self.settings = settings or get_settings()
        self.logger = _setup_llm_logger(self.settings)

    async def generate(self, prompt: str, system: str | None = None, max_tokens: int = 2048) -> LLMResponse:
        """Generate using Anthropic API."""
        start_time = time.time()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Log request
        self.logger.info(f"[{timestamp}] REQUEST")
        self.logger.info(f"Provider: anthropic")
        self.logger.info(f"Model: {self.model}")
        if system:
            self.logger.info(f"System Prompt: {system}")
        self.logger.info(f"User Prompt: {prompt}")
        self.logger.info(f"Max Tokens: {max_tokens}")
        self.logger.info("")

        try:
            kwargs = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                kwargs["system"] = system

            response = await self.client.messages.create(**kwargs)

            duration_ms = int((time.time() - start_time) * 1000)
            response_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            # Log response
            self.logger.info(f"[{response_timestamp}] RESPONSE")
            self.logger.info(f"Success: True")
            self.logger.info(f"Content: {response.content[0].text}")
            self.logger.info(f"Input Tokens: {response.usage.input_tokens}")
            self.logger.info(f"Output Tokens: {response.usage.output_tokens}")
            self.logger.info(f"Duration: {duration_ms}ms")
            self.logger.info("")
            self.logger.info("=" * 80)
            self.logger.info("")

            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            # Log error
            self.logger.info(f"[{error_timestamp}] RESPONSE")
            self.logger.info(f"Success: False")
            self.logger.info(f"Error: {str(e)}")
            self.logger.info(f"Duration: {duration_ms}ms")
            self.logger.info("")
            self.logger.info("=" * 80)
            self.logger.info("")

            raise


class OpenAICompatibleClient(LLMClient):
    """OpenAI-compatible API client (works with vLLM, local inference, etc.)."""

    def __init__(self, api_key: str, base_url: str | None = None, model: str = "gpt-4", settings: Settings | None = None) -> None:
        self.client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.settings = settings or get_settings()
        self.logger = _setup_llm_logger(self.settings)

    async def generate(self, prompt: str, system: str | None = None, max_tokens: int = 2048) -> LLMResponse:
        """Generate using OpenAI-compatible API."""
        start_time = time.time()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Log request
        self.logger.info(f"[{timestamp}] REQUEST")
        self.logger.info(f"Provider: openai")
        self.logger.info(f"Model: {self.model}")
        if system:
            self.logger.info(f"System Prompt: {system}")
        self.logger.info(f"User Prompt: {prompt}")
        self.logger.info(f"Max Tokens: {max_tokens}")
        self.logger.info("")

        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
            )

            duration_ms = int((time.time() - start_time) * 1000)
            response_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            # Log response
            self.logger.info(f"[{response_timestamp}] RESPONSE")
            self.logger.info(f"Success: True")
            self.logger.info(f"Content: {response.choices[0].message.content}")
            self.logger.info(f"Input Tokens: {response.usage.prompt_tokens if response.usage else 0}")
            self.logger.info(f"Output Tokens: {response.usage.completion_tokens if response.usage else 0}")
            self.logger.info(f"Duration: {duration_ms}ms")
            self.logger.info("")
            self.logger.info("=" * 80)
            self.logger.info("")

            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            # Log error
            self.logger.info(f"[{error_timestamp}] RESPONSE")
            self.logger.info(f"Success: False")
            self.logger.info(f"Error: {str(e)}")
            self.logger.info(f"Duration: {duration_ms}ms")
            self.logger.info("")
            self.logger.info("=" * 80)
            self.logger.info("")

            raise


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
            settings=settings,
        )
    elif settings.llm_provider == "openai":
        return OpenAICompatibleClient(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            settings=settings,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
