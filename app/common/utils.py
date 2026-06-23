import os
import uuid
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Any
from dotenv import load_dotenv
from functools import lru_cache
from langchain.messages import RemoveMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.prompts import PromptTemplate
from typing import List, Set
load_dotenv()


# TODO(qwen): add a 'qwen' branch here (DashScope OpenAI-compatible endpoint)
# and switch the default provider. Keeping the Gemini branch for now so the
# existing pipeline keeps working until we wire Qwen credentials.
@lru_cache(maxsize = 1)
def _get_model(
    name: str,
    temp: Optional[float] = None,
    max_tokens: Optional[int] = None
):
    if name == 'google':
        kwargs = {
            "api_key": os.getenv("GEMINI_API_KEY"),
            "model": "gemini-3-flash-preview",
            "max_retries": 2,
            "temperature": 1.0,
            "max_tokens": None,
            "timeout": None,
            "thinking_level": "low",
            "include_thoughts": False
        }
        if temp is not None:
            kwargs["temperature"] = temp
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        model = ChatGoogleGenerativeAI(**kwargs)

    elif name == 'qwen':
        # Qwen via Alibaba Cloud DashScope (OpenAI-compatible endpoint).
        # Lazy import so the module doesn't hard-require langchain-openai
        # unless the Qwen provider is actually used.
        from langchain_openai import ChatOpenAI

        kwargs = {
            "api_key": os.getenv("DASHSCOPE_API_KEY"),
            "base_url": os.getenv(
                "DASHSCOPE_BASE_URL",
                "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            ),
            "model": os.getenv("QWEN_MODEL", "qwen-plus"),
            "temperature": 0,
            "max_retries": 2,
            "timeout": None,
        }
        if temp is not None:
            kwargs["temperature"] = temp
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        model = ChatOpenAI(**kwargs)

    else:
        raise ValueError(f"Unsupported Model Name: {name}")

    return model


def _llm_call(
    system_prompt: str,
    user_prompt_template: str,
    user_prompt_inputs: dict,
    llm : Any,
    schema : Any,
    structured_output: bool = False
):

    user_prompt = PromptTemplate(
        input_variables = user_prompt_inputs.keys(),
        template = user_prompt_template
    )

    formatted_user_prompt = user_prompt.format(**user_prompt_inputs)
    messages = [SystemMessage(content = system_prompt), HumanMessage(content = formatted_user_prompt)]

    try:
        if not structured_output:
            response = llm.invoke(messages)
        else:
            structured_llm = llm.with_structured_output(schema)
            response = structured_llm.invoke(messages)

    except Exception as e:
        print(f'Error during LLM call: {e}')
        response = None

    return response


def trim_messages(state):
    """
    Trim messages in the state if there are 8 or more human messages.
    - Remove all messages from the first human up to before the 4th human.
    - Return the updated state dict.
    """
    messages = state["messages"]

    human_indices = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]

    if len(human_indices) < 8:
        return state["messages"]

    fourth_human_idx = human_indices[3]

    messages_to_remove = messages[:fourth_human_idx]

    remove_objects = [RemoveMessage(id = m.id) for m in messages_to_remove]

    return {"messages": remove_objects}


def filter_agent_messages(messages: List, blocked_tools: Set[str]) -> List:
    # Collect all IDs of AI messages that need blocking
    blocked_ids = set()
    output_messages = []
    for m in messages:
        if isinstance(m, AIMessage):
            # Check if content exists and is a list
            if m.content and isinstance(m.content, list):
                for c in m.content:
                    # Check if it's a function_call and the name is in blocked_tools
                    if c.get("type") == "function_call" and c.get("name") in blocked_tools:
                        blocked_ids.add(c.get("call_id"))
                        continue
                    else:
                        output_messages.append(m)
        elif isinstance(m, ToolMessage):
            if m.name in blocked_tools:
                blocked_ids.add(m.tool_call_id)
                continue
            else:
                output_messages.append(m)
        elif isinstance(m, HumanMessage):
            output_messages.append(m)
    #print("output_messagres", output_messages)
    return output_messages
