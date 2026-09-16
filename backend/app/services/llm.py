"""
LLM Service - Provides LLM client initialization with support for multiple providers.
Supports NVIDIA NIM, Google Gemini, and Groq.
"""

from typing import Optional, Any, Dict, Type, Union
import json
import logging
from pydantic import BaseModel
from app.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Custom exception for LLM errors."""
    pass


class LLMClientWrapper:
    """Wrapper around different LLM providers to provide unified call interface."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        api_key: Optional[str] = None,
        provider: Optional[str] = None
    ):
        self.provider = provider or settings.LLM_PROVIDER
        self.temperature = temperature or settings.LLM_TEMPERATURE
        
        if self.provider == "nvidia":
            # NVIDIA NIM configuration
            from openai import AsyncOpenAI, OpenAI
            
            self.model_name = model_name or settings.NVIDIA_MODEL
            self.api_key = api_key or settings.NVIDIA_API_KEY
            self.base_url = settings.NVIDIA_BASE_URL
            
            self.async_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=30.0,  # 30 second timeout
                max_retries=2   # Retry failed requests
            )
            
            self.sync_client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=30.0,  # 30 second timeout
                max_retries=2   # Retry failed requests
            )
            
        elif self.provider == "gemini":
            # Gemini configuration
            from google import genai
            from google.genai import types
            
            self.model_name = model_name or settings.GEMINI_MODEL
            self.api_key = api_key or settings.GEMINI_API_KEY
            
            self.client = genai.Client(api_key=self.api_key)
            self.generation_config = types.GenerateContentConfig(
                temperature=self.temperature,
                top_p=0.95,
                top_k=40,
                max_output_tokens=8192,
            )
            
        else:
            raise LLMError(f"Unsupported LLM provider: {self.provider}")

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Optional[Type[BaseModel]] = None
    ) -> Union[Dict[str, Any], str]:
        """Execute LLM call with optional structured output schema."""
        try:
            if self.provider == "nvidia":
                # NVIDIA NIM API call - combine system and user prompts
                combined_prompt = f"{system_prompt}\n\n{user_prompt}"
                
                if response_schema:
                    combined_prompt += f"\n\nRespond ONLY with valid JSON matching this schema: {response_schema.model_json_schema()}"
                
                messages = [
                    {"role": "user", "content": combined_prompt}
                ]
                
                response = await self.async_client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=8192
                )
                
                response_text = response.choices[0].message.content
                
                if response_schema:
                    try:
                        # Parse JSON response
                        json_text = response_text.strip()
                        if json_text.startswith("```json"):
                            json_text = json_text.split("```json")[1].split("```")[0].strip()
                        elif json_text.startswith("```"):
                            json_text = json_text.split("```")[1].split("```")[0].strip()
                        
                        parsed = json.loads(json_text)
                        return parsed
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON response: {e}. Raw: {response_text[:200]}")
                        return {}
                else:
                    return response_text
                    
            elif self.provider == "gemini":
                # Gemini API call
                full_prompt = f"{system_prompt}\n\n{user_prompt}"
                
                if response_schema:
                    full_prompt += f"\n\nRespond ONLY with valid JSON matching this schema: {response_schema.model_json_schema()}"
                
                response = await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=full_prompt,
                    config=self.generation_config
                )
                
                response_text = response.text
                
                if response_schema:
                    try:
                        json_text = response_text.strip()
                        if json_text.startswith("```json"):
                            json_text = json_text.split("```json")[1].split("```")[0].strip()
                        elif json_text.startswith("```"):
                            json_text = json_text.split("```")[1].split("```")[0].strip()
                        
                        parsed = json.loads(json_text)
                        return parsed
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON response: {e}. Raw: {response_text[:200]}")
                        return {}
                else:
                    return response_text
                    
        except Exception as e:
            logger.error(f"{self.provider.upper()} LLM call failed: {e}")
            raise LLMError(f"LLM call error: {e}") from e

    async def ainvoke(self, input_val: Any, config: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Any:
        """Async invoke for LangChain compatibility."""
        try:
            if self.provider == "nvidia":
                if isinstance(input_val, list):
                    # Handle LangChain message format
                    messages = []
                    for msg in input_val:
                        if hasattr(msg, 'content'):
                            role = "assistant" if hasattr(msg, 'type') and msg.type == "ai" else "user"
                            if hasattr(msg, 'type') and msg.type == "system":
                                role = "system"
                            messages.append({"role": role, "content": msg.content})
                        elif isinstance(msg, dict):
                            messages.append(msg)
                        else:
                            messages.append({"role": "user", "content": str(msg)})
                    
                    response = await self.async_client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=8192
                    )
                else:
                    messages = [{"role": "user", "content": str(input_val)}]
                    response = await self.async_client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=8192
                    )
                
                # Return LangChain-compatible response
                class AIMessage:
                    def __init__(self, content):
                        self.content = content
                
                return AIMessage(response.choices[0].message.content)
                
            elif self.provider == "gemini":
                if isinstance(input_val, list):
                    messages_text = ""
                    for msg in input_val:
                        if hasattr(msg, 'content'):
                            messages_text += f"{msg.content}\n"
                        elif isinstance(msg, dict):
                            messages_text += f"{msg.get('content', '')}\n"
                        else:
                            messages_text += f"{str(msg)}\n"
                    
                    response = await self.client.aio.models.generate_content(
                        model=self.model_name,
                        contents=messages_text.strip(),
                        config=self.generation_config
                    )
                else:
                    response = await self.client.aio.models.generate_content(
                        model=self.model_name,
                        contents=str(input_val),
                        config=self.generation_config
                    )
                
                class AIMessage:
                    def __init__(self, content):
                        self.content = content
                
                return AIMessage(response.text)
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"{self.provider.upper()} ainvoke failed: {e}")
            
            # Handle specific error types
            if "504" in error_msg or "timeout" in error_msg.lower():
                raise LLMError(f"LLM service timeout (504): The {self.provider.upper()} API is temporarily overloaded. Please try again in a moment.") from e
            elif "502" in error_msg or "503" in error_msg:
                raise LLMError(f"LLM service unavailable ({self.provider.upper()} API): Temporary service issue. Please try again.") from e
            elif "429" in error_msg:
                raise LLMError(f"LLM rate limit exceeded ({self.provider.upper()}): Too many requests. Please wait before retrying.") from e
            else:
                raise LLMError(f"LLM ainvoke error: {e}") from e

    def invoke(self, input_val: Any, config: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Any:
        """Sync invoke for LangChain compatibility."""
        try:
            if self.provider == "nvidia":
                if isinstance(input_val, list):
                    messages = []
                    for msg in input_val:
                        if hasattr(msg, 'content'):
                            role = "assistant" if hasattr(msg, 'type') and msg.type == "ai" else "user"
                            if hasattr(msg, 'type') and msg.type == "system":
                                role = "system"
                            messages.append({"role": role, "content": msg.content})
                        elif isinstance(msg, dict):
                            messages.append(msg)
                        else:
                            messages.append({"role": "user", "content": str(msg)})
                    
                    response = self.sync_client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=8192
                    )
                else:
                    messages = [{"role": "user", "content": str(input_val)}]
                    response = self.sync_client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=8192
                    )
                
                class AIMessage:
                    def __init__(self, content):
                        self.content = content
                
                return AIMessage(response.choices[0].message.content)
                
            elif self.provider == "gemini":
                if isinstance(input_val, list):
                    messages_text = ""
                    for msg in input_val:
                        if hasattr(msg, 'content'):
                            messages_text += f"{msg.content}\n"
                        elif isinstance(msg, dict):
                            messages_text += f"{msg.get('content', '')}\n"
                        else:
                            messages_text += f"{str(msg)}\n"
                    
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=messages_text.strip(),
                        config=self.generation_config
                    )
                else:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=str(input_val),
                        config=self.generation_config
                    )
                
                class AIMessage:
                    def __init__(self, content):
                        self.content = content
                
                return AIMessage(response.text)
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"{self.provider.upper()} invoke failed: {e}")
            
            # Handle specific error types
            if "504" in error_msg or "timeout" in error_msg.lower():
                raise LLMError(f"LLM service timeout (504): The {self.provider.upper()} API is temporarily overloaded. Please try again in a moment.") from e
            elif "502" in error_msg or "503" in error_msg:
                raise LLMError(f"LLM service unavailable ({self.provider.upper()} API): Temporary service issue. Please try again.") from e
            elif "429" in error_msg:
                raise LLMError(f"LLM rate limit exceeded ({self.provider.upper()}): Too many requests. Please wait before retrying.") from e
            else:
                raise LLMError(f"LLM invoke error: {e}") from e

    def with_structured_output(self, schema: Any, **kwargs: Any) -> 'LLMClientWrapper':
        """Return self for structured output (handled in call method)."""
        return self


def get_llm_client(
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    api_key: Optional[str] = None,
    provider: Optional[str] = None
) -> LLMClientWrapper:
    """Get configured LLM client wrapper."""
    return LLMClientWrapper(
        model_name=model_name,
        temperature=temperature,
        api_key=api_key,
        provider=provider
    )


def get_llm_for_agent(agent_name: str, temperature: Optional[float] = None) -> LLMClientWrapper:
    """Get LLM client configured for a specific agent."""
    agent_temperatures = {
        "router": 0.0,
        "intake": 0.1,
        "lookup": 0.2,
        "planner": 0.3,
        "search": 0.2,
        "quant": 0.1,
        "source_tier": 0.0,
        "writer": 0.4,
        "originality": 0.1,
        "critic": 0.2,
    }
    agent_temp = temperature or agent_temperatures.get(agent_name, settings.LLM_TEMPERATURE)
    
    if settings.LLM_PROVIDER == "nvidia":
        return LLMClientWrapper(
            model_name=settings.NVIDIA_MODEL,
            temperature=agent_temp,
            api_key=settings.NVIDIA_API_KEY,
            provider="nvidia"
        )
    elif settings.LLM_PROVIDER == "gemini":
        return LLMClientWrapper(
            model_name=settings.GEMINI_MODEL,
            temperature=agent_temp,
            api_key=settings.GEMINI_API_KEY,
            provider="gemini"
        )
    else:
        raise LLMError(f"Unsupported LLM provider: {settings.LLM_PROVIDER}")