"""
Abstract base class for LLM clients.
All LLM implementations should extend this class.
"""

import logging
import os
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Type, Union

from dotenv import load_dotenv
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
load_dotenv()

class MissingQueryVariableError(Exception):
    """Raised when query is missing required variables from prompt template."""
    pass


@dataclass
class PromptTemplate:
    """Dataclass for prompt template components."""
    prompt_name: str
    system_prompt: str
    human_template: str
    model_config: Dict[str, Any]
    input_variables: List[str]


class LLMClient(ABC):
    """
    Abstract base class for LLM clients.

    All LLM implementations should extend this class and implement the chat() method.
    The base class provides:
    - Message formatting support
    - Prompt template handling
    - Query validation
    - Optional methods for streaming and batch operations
    """

    def __init__(self,
                 prompt_template: Optional[PromptTemplate] = None,
                 structured_output_schema: Optional[Type[BaseModel]] = None):
        """
        Initialize LLM client.

        Args:
            prompt_template: Optional PromptTemplate with system prompt, human template, and model config
            structured_output_schema: Optional Pydantic model class for structured output
        """
        self.prompt_template = prompt_template
        self.structured_output_schema = structured_output_schema

    @abstractmethod
    def chat(self, query: Dict[str, Any]) -> Union[str, BaseModel]:
        """
        Process single query synchronously.

        Args:
            query: Query dictionary with variables for prompt template

        Returns:
            Complete response text (str) or structured output (BaseModel instance)

        Raises:
            MissingQueryVariableError: If query is missing required variables

        Note:
            Must be implemented by child classes.
        """
        pass

    def _create_messages(self, query: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Create message list from query using the prompt template.

        This method now supports formatting of both the system prompt and the human/user
        template using the provided query variables. If the system prompt contains
        placeholders (e.g. "{branching}") they will be formatted with values from query.

        Args:
            query: Dictionary containing variables needed by the prompt template

        Returns:
            List of message dicts in format:
            [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]

        Raises:
            MissingQueryVariableError: If query is missing required variables referenced by the
                                      prompt template or system prompt formatting fails.
        """
        if not self.prompt_template:
            raise ValueError("prompt_template is required to create messages")

        # Validate that query contains all required variables declared by the template.
        missing_vars = set(self.prompt_template.input_variables) - set(query.keys())
        if missing_vars:
            raise MissingQueryVariableError(
                f"Query is missing required variables: {', '.join(sorted(missing_vars))}. "
                f"Required variables: {', '.join(sorted(self.prompt_template.input_variables))}"
            )

        # Format system prompt (allow it to be parameterized)
        system_template = self.prompt_template.system_prompt or ""
        try:
            system_content = system_template.format(**query) if system_template else system_template
        except KeyError as exc:
            # Provide a clear message about which variable is missing for system prompt formatting
            var_name = exc.args[0] if exc.args else "<unknown>"
            raise MissingQueryVariableError(
                f"System prompt formatting failed, missing variable: {var_name}"
            ) from exc

        # Format human template with query variables
        try:
            user_content = self.prompt_template.human_template.format(**query)
        except KeyError as exc:
            var_name = exc.args[0] if exc.args else "<unknown>"
            raise MissingQueryVariableError(
                f"Human template formatting failed, missing variable: {var_name}"
            ) from exc

        messages: List[Dict[str, str]] = []
        if system_content:
            messages.append({"role": "system", "content": system_content})
        # Always include the user message
        messages.append({"role": "user", "content": user_content})

        return messages


    def batch(self, queries: List[Dict[str, Any]]) -> List[Union[str, BaseModel]]:
        """
        Process multiple queries synchronously.

        Args:
            queries: List of query dictionaries

        Returns:
            List of responses (str or BaseModel instances)

        Raises:
            NotImplementedError: If batch processing is not implemented for this client
        """
        raise NotImplementedError(f"Batch processing not implemented for {self.__class__.__name__}")


class LangchainLLMClient(LLMClient):
    """
    LangChain-based LLM client supporting multiple providers (Anthropic, OpenAI).

    Supports:
    1. Invoke - single synchronous request
    2. Stream - single streaming request
    3. Batch - multiple synchronous requests
    4. AInvoke - single async request
    5. AStream - single async streaming request
    6. ABatch - multiple async requests

    Supports both raw text output and structured output via Pydantic models.
    """

    def __init__(self,
                 prompt_template: PromptTemplate,
                 provider: str = "glm",
                 structured_output_schema: Optional[Type[BaseModel]] = None):
        """
        Initialize LangChain LLM client.

        Args:
            prompt_template: PromptTemplate with system prompt, human template, and model config
            llm: LangChain LLM instance (creates new if None)
            provider: LLM provider ("anthropic" or "openai")
            structured_output_schema: Optional Pydantic model class for structured output

        Raises:
            ValueError: If prompt_template is not provided
        """
        if not prompt_template:
            raise ValueError("prompt_template is required")

        super().__init__(prompt_template, structured_output_schema)

        self.provider = provider
        model_config = self.prompt_template.model_config or {}

        self.llm = self._create_llm(self.provider, model_config)
        #logger.info(f"Created LangChain LLM client with provider: {self.provider}")

        # Create structured output model if requested
        if self.structured_output_schema:
            if self.provider == "glm" or self.provider == "qwen" or self.provider == 'baidu':
                self.structured_llm = self.llm.with_structured_output(self.structured_output_schema, method="function_calling")
            else:
                self.structured_llm = self.llm.with_structured_output(self.structured_output_schema)
        else:
            self.structured_llm = None

    def _create_llm(self, provider: str, model_config: Dict[str, Any]) -> BaseLanguageModel:
        """
        Create LLM instance based on provider and configuration.

        Args:
            provider: LLM provider ("anthropic" or "openai")
            model_config: Optional model configuration dictionary

        Returns:
            BaseLanguageModel instance

        Raises:
            ValueError: If provider is not supported
            RuntimeError: If model instantiation fails
        """

        provider_lower = provider.lower()
        print(f"provider_lower: {provider_lower}")

        if provider_lower == "glm":
            return ChatOpenAI(
                base_url="https://open.bigmodel.cn/api/paas/v4/",
                api_key=os.getenv("GLM_API_KEY"),
                model=model_config.get("model", "glm-4-plus"),
                max_tokens=model_config.get("max_tokens", 4096),
                temperature=model_config.get("temperature", 0.25)
            )

        elif provider == "openai":
            return ChatOpenAI(
                    base_url="https://api2.aigcbest.top/v1",
                    api_key=os.getenv("OPENAI_API_KEY_FOR_CLARA"),
                    model=model_config.get("model"),
                    max_tokens=model_config.get("max_tokens"),
                    temperature=model_config.get("temperature")
                )

        raise ValueError(f"Unsupported provider: {provider}. Currently only 'glm' is implemented.")

    def _convert_to_langchain_messages(self, messages: List[Dict[str, str]]) -> List:
        """
        Convert standard message dicts to LangChain message objects.

        Args:
            messages: List of message dicts with "role" and "content" keys

        Returns:
            List of LangChain message objects (SystemMessage, HumanMessage)
        """
        langchain_messages = []
        for msg in messages:
            if msg["role"] == "system":
                langchain_messages.append(SystemMessage(content=msg["content"]))
            elif msg["role"] == "user":
                langchain_messages.append(HumanMessage(content=msg["content"]))
            else:
                logger.warning(f"Unknown message role: {msg['role']}, treating as user message")
                langchain_messages.append(HumanMessage(content=msg["content"]))
        return langchain_messages

    def chat(self, query: Dict[str, Any]) -> Union[str, BaseModel]:
        """
        Process single query synchronously using LangChain.

        Args:
            query: Query dictionary with variables for prompt template

        Returns:
            Complete response text (str) or structured output (BaseModel instance)

        Raises:
            MissingQueryVariableError: If query is missing required variables
        """
        # Create standard message format
        messages = self._create_messages(query)

        # Convert to LangChain format
        langchain_messages = self._convert_to_langchain_messages(messages)

        if self.structured_llm:
            return self.structured_llm.invoke(langchain_messages)
        else:
            response = self.llm.invoke(langchain_messages)
            return response.content

    
    def batch(self, queries: List[Dict[str, Any]]) -> List[Union[str, BaseModel]]:
        """
        Process multiple queries synchronously using LangChain batch.

        Args:
            queries: List of query dictionaries

        Returns:
            List of responses (str or BaseModel instances)
        """
        all_messages = []
        for query in queries:
            messages = self._create_messages(query)
            langchain_messages = self._convert_to_langchain_messages(messages)
            all_messages.append(langchain_messages)

        if self.structured_llm:
            return self.structured_llm.batch(all_messages)
        else:
            responses = self.llm.batch(all_messages)
            return [response.content for response in responses]


