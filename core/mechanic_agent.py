"""
ASE Certified Mechanic Agent (Tier 2 -- LLM-Powered)
A conversational AI agent with the persona of an ASE Certified Master
Technician. Provides expert-level automotive diagnostic guidance through
natural conversation.

Architecture:
- Pluggable LLM backends (OpenAI, Anthropic, Ollama)
- Tavily web search for TSBs, recalls, and vehicle-specific issues
- Structured tool-calling for OBD-II code lookup, diagnosis context,
  and knowledge base search
- Conversation memory with context window management
- Guardrails: always recommends professional inspection for safety items

DISABLED BY DEFAULT. Requires API keys to function.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from core.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System Prompt (ASE Master Technician Persona)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an ASE Certified Master Technician with 25+ years of experience \
diagnosing and repairing all makes and models. Your name is "DiagBot" and \
you work at a virtual diagnostic shop.

PERSONALITY:
- Friendly, patient, and professional -- like a trusted local mechanic
- Explain things clearly without being condescending
- Use real-world analogies to help non-technical users understand
- If asked about pricing, give general ranges but note they vary by region
- Always empathize: "I understand that can be frustrating" / "Good catch noticing that"

DIAGNOSTIC APPROACH:
- Ask clarifying questions to narrow down the issue (one or two at a time)
- Reference the audio analysis results when available
- Suggest the most likely cause first, then alternatives
- Prioritize safety-critical issues (brakes, steering, suspension)
- When uncertain, say so honestly rather than guessing

TOOL USAGE:
- Use the lookup_trouble_code tool when the user mentions a DTC
- Use the search_web tool to find TSBs, recalls, or model-specific issues
- Use the get_diagnosis_results tool to reference the audio analysis
- Use the search_knowledge_base tool for repair procedures and diagnostic trees

GUARDRAILS:
- NEVER diagnose brake failure, steering loss, or airbag issues without \
  recommending immediate professional inspection
- NEVER recommend repairs beyond the user's stated skill level
- ALWAYS suggest a professional mechanic for safety-critical systems
- If the user describes a dangerous condition (e.g., smoke, fluid leaks near \
  hot components), advise them to stop driving immediately
- Do NOT fabricate TSB numbers or recall numbers -- only cite real ones from search results

OUTPUT FORMAT:
- Keep responses concise (2-4 paragraphs max)
- Use bullet points for lists of possible causes
- Bold the most likely diagnosis
- End with a clear next-step recommendation
"""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """A single message in the conversation."""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    tool_call_id: str = ""
    name: str = ""  # tool name for tool responses


@dataclass
class ConversationMemory:
    """Manages conversation history with context window limits."""
    messages: list[Message] = field(default_factory=list)
    max_messages: int = 50  # Keep last N messages

    def add(self, message: Message):
        self.messages.append(message)
        # Trim old messages but always keep the system prompt
        if len(self.messages) > self.max_messages:
            system_msgs = [m for m in self.messages if m.role == "system"]
            recent = self.messages[-(self.max_messages - len(system_msgs)):]
            self.messages = system_msgs + recent

    def get_messages_for_api(self) -> list[dict]:
        """Convert to API-compatible message format."""
        api_messages = []
        for m in self.messages:
            msg = {"role": m.role, "content": m.content}
            if m.tool_calls:
                msg["tool_calls"] = m.tool_calls
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            if m.name:
                msg["name"] = m.name
            api_messages.append(msg)
        return api_messages

    def clear(self):
        """Clear all messages except system prompt."""
        self.messages = [m for m in self.messages if m.role == "system"]


# ---------------------------------------------------------------------------
# Tool Definitions (for structured tool-calling)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_trouble_code",
            "description": (
                "Look up an OBD-II diagnostic trouble code to get its "
                "description, affected system, related mechanical classes, "
                "common symptoms, and severity level."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The OBD-II code (e.g. P0301, C0035)",
                    }
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the web for automotive information including TSBs "
                "(Technical Service Bulletins), recalls, common problems "
                "for specific vehicles, and repair procedures. Use this "
                "when the user mentions a specific vehicle make/model/year."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g. '2018 Toyota Camry timing chain rattle TSB')",
                    },
                    "vehicle_info": {
                        "type": "string",
                        "description": "Vehicle year/make/model if known",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_diagnosis_results",
            "description": (
                "Retrieve the most recent audio diagnosis results including "
                "mechanical class scores, extracted audio features, applied "
                "penalties, and fingerprint matches."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": (
                "Search the local knowledge base for diagnostic trees, "
                "repair procedures, common failure patterns, and symptom "
                "guides. Best for general automotive knowledge."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for (e.g. 'wheel bearing diagnosis procedure')",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# MechanicAgent class
# ---------------------------------------------------------------------------

class MechanicAgent:
    """
    ASE Certified Mechanic conversational agent.

    Usage:
        agent = MechanicAgent(db_manager=db_mgr)
        response = agent.chat("My car makes a grinding noise when braking")
    """

    def __init__(
        self,
        db_manager=None,
        llm_provider: str | None = None,
        diagnosis_result: Any = None,
    ):
        self.db_manager = db_manager
        settings = get_settings().agent
        self.llm_provider = llm_provider or settings.agent_llm_provider
        self.memory = ConversationMemory()
        self._diagnosis_result = diagnosis_result
        self._knowledge_base = None  # Lazy-loaded

        # Initialize with system prompt
        self.memory.add(Message(role="system", content=SYSTEM_PROMPT))

    @property
    def is_available(self) -> bool:
        """Check if the agent has a configured LLM backend."""
        if not self.llm_provider:
            return False
        settings = get_settings()
        if self.llm_provider == "openai":
            return bool(settings.llm.openai_api_key)
        if self.llm_provider == "anthropic":
            return bool(settings.llm.anthropic_api_key)
        if self.llm_provider == "ollama":
            return True  # Assume local Ollama is available
        return False

    def set_diagnosis_result(self, result):
        """Update the current diagnosis result for context."""
        self._diagnosis_result = result

    def chat(
        self,
        user_message: str,
        on_tool_call: Callable[[str, dict], None] | None = None,
    ) -> str:
        """
        Send a user message and get the agent's response.

        Args:
            user_message: The user's text.
            on_tool_call: Optional callback(tool_name, args) for UI updates.

        Returns:
            The agent's response text.
        """
        # Add user message to memory
        self.memory.add(Message(role="user", content=user_message))

        # If LLM not available, use fallback
        if not self.is_available:
            return self._fallback_response(user_message)

        # Call LLM with tool support
        try:
            response = self._call_llm_with_tools(on_tool_call)
            self.memory.add(Message(role="assistant", content=response))
            return response
        except Exception as e:
            error_msg = (
                f"I'm having trouble connecting to my diagnostic systems "
                f"right now. Error: {e}\n\n"
                f"In the meantime, based on what you've described, "
                f"I'd recommend having a qualified technician take a look."
            )
            self.memory.add(Message(role="assistant", content=error_msg))
            return error_msg

    def reset_conversation(self):
        """Start a fresh conversation."""
        self.memory.clear()

    # ------------------------------------------------------------------
    # LLM calling with tool support
    # ------------------------------------------------------------------

    def _call_llm_with_tools(
        self,
        on_tool_call: Callable | None = None,
        max_tool_rounds: int = 3,
    ) -> str:
        """
        Call the LLM, handle any tool calls, and return final response.
        Supports multiple rounds of tool calling.
        """
        for _ in range(max_tool_rounds):
            messages = self.memory.get_messages_for_api()

            if self.llm_provider == "openai":
                result = self._call_openai(messages)
            elif self.llm_provider == "anthropic":
                result = self._call_anthropic(messages)
            elif self.llm_provider == "ollama":
                result = self._call_ollama(messages)
            else:
                return "LLM provider not configured."

            # If no tool calls, return the text
            if not result.get("tool_calls"):
                return result.get("content", "")

            # Process tool calls
            assistant_msg = Message(
                role="assistant",
                content=result.get("content", ""),
                tool_calls=result["tool_calls"],
            )
            self.memory.add(assistant_msg)

            for tc in result["tool_calls"]:
                tool_name = tc["function"]["name"]
                try:
                    tool_args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    tool_args = {}

                if on_tool_call:
                    on_tool_call(tool_name, tool_args)

                # Execute the tool
                tool_result = self._execute_tool(tool_name, tool_args)

                # Add tool result to memory
                self.memory.add(Message(
                    role="tool",
                    content=json.dumps(tool_result, default=str),
                    tool_call_id=tc.get("id", ""),
                    name=tool_name,
                ))

        # If we exhausted tool rounds, get final response
        messages = self.memory.get_messages_for_api()
        if self.llm_provider == "openai":
            result = self._call_openai(messages, tools=False)
        elif self.llm_provider == "anthropic":
            result = self._call_anthropic(messages, tools=False)
        else:
            result = self._call_ollama(messages)

        return result.get("content", "")

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tool(self, name: str, args: dict) -> dict:
        """Execute a tool and return its result."""
        try:
            if name == "lookup_trouble_code":
                return self._tool_lookup_code(args.get("code", ""))
            elif name == "search_web":
                return self._tool_search_web(
                    args.get("query", ""),
                    args.get("vehicle_info", ""),
                )
            elif name == "get_diagnosis_results":
                return self._tool_get_diagnosis()
            elif name == "search_knowledge_base":
                return self._tool_search_kb(args.get("query", ""))
            else:
                return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            return {"error": str(e)}

    def _tool_lookup_code(self, code: str) -> dict:
        """Look up a trouble code from the database."""
        if not self.db_manager:
            return {"error": "Database not available"}

        try:
            from database.trouble_code_lookup import lookup_code
            defn = lookup_code(code, self.db_manager)
            if defn is None:
                return {"code": code, "found": False, "message": "Code not in database"}
            return {
                "code": defn.code,
                "found": True,
                "description": defn.description,
                "system": defn.system,
                "subsystem": defn.subsystem,
                "mechanical_classes": defn.mechanical_classes,
                "symptoms": defn.symptoms,
                "severity": defn.severity,
            }
        except Exception as e:
            return {"error": str(e)}

    def _tool_search_web(self, query: str, vehicle_info: str = "") -> dict:
        """Search the web via Tavily."""
        try:
            from core.tavily_search import search_automotive
            results = search_automotive(query, vehicle_info)
            return {
                "query": query,
                "results": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet,
                    }
                    for r in results[:5]
                ],
            }
        except ImportError:
            return {"error": "Tavily search module not available"}
        except Exception as e:
            return {"error": f"Web search failed: {e}"}

    def _tool_get_diagnosis(self) -> dict:
        """Return the current diagnosis results."""
        if self._diagnosis_result is None:
            return {"available": False, "message": "No audio analysis has been run yet"}

        result = self._diagnosis_result
        return {
            "available": True,
            "top_class": result.top_class,
            "confidence": result.confidence,
            "is_ambiguous": result.is_ambiguous,
            "class_scores": {
                k: round(v, 4) for k, v in result.class_scores.items()
            },
            "fingerprint_count": result.fingerprint_count,
            "top_penalties": {
                k: round(v, 4) for k, v in result.penalties_applied.items()
                if v > 0
            },
        }

    def _tool_search_kb(self, query: str) -> dict:
        """Search the local knowledge base."""
        try:
            if self._knowledge_base is None:
                from core.knowledge_base import KnowledgeBase
                self._knowledge_base = KnowledgeBase()

            chunks = self._knowledge_base.retrieve(query, max_chunks=3)
            return {
                "query": query,
                "results": [
                    {
                        "title": c.title,
                        "content": c.content[:500],
                        "category": c.category,
                        "relevance": round(c.relevance, 3),
                    }
                    for c in chunks
                ],
            }
        except ImportError:
            return {"error": "Knowledge base module not available"}
        except Exception as e:
            return {"error": f"Knowledge base search failed: {e}"}

    # ------------------------------------------------------------------
    # LLM backend calls
    # ------------------------------------------------------------------

    def _call_openai(self, messages: list[dict], tools: bool = True) -> dict:
        """Call OpenAI API with tool support."""
        try:
            import openai
        except ImportError:
            return {"content": "[OpenAI package not installed. Run: pip install openai]"}

        settings = get_settings()
        api_key = settings.llm.openai_api_key
        if not api_key:
            return {"content": "[Set OPENAI_API_KEY environment variable]"}

        client = openai.OpenAI(api_key=api_key)

        kwargs = {
            "model": settings.agent.mechanic_openai_model,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 1500,
        }
        if tools:
            kwargs["tools"] = TOOL_DEFINITIONS
            kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        result = {"content": choice.message.content or ""}

        if choice.message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        return result

    def _call_anthropic(self, messages: list[dict], tools: bool = True) -> dict:
        """Call Anthropic API with tool support."""
        try:
            import anthropic
        except ImportError:
            return {"content": "[Anthropic package not installed. Run: pip install anthropic]"}

        settings = get_settings()
        api_key = settings.llm.anthropic_api_key
        if not api_key:
            return {"content": "[Set ANTHROPIC_API_KEY environment variable]"}

        client = anthropic.Anthropic(api_key=api_key)

        # Anthropic uses a different tool format
        system_msg = ""
        api_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                api_messages.append(m)

        kwargs = {
            "model": settings.agent.mechanic_anthropic_model,
            "max_tokens": 1500,
            "system": system_msg,
            "messages": api_messages,
        }

        if tools:
            # Convert tool definitions to Anthropic format
            anthropic_tools = []
            for td in TOOL_DEFINITIONS:
                anthropic_tools.append({
                    "name": td["function"]["name"],
                    "description": td["function"]["description"],
                    "input_schema": td["function"]["parameters"],
                })
            kwargs["tools"] = anthropic_tools

        response = client.messages.create(**kwargs)

        result = {"content": ""}
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                result["content"] += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input),
                    },
                })

        if tool_calls:
            result["tool_calls"] = tool_calls

        return result

    def _call_ollama(self, messages: list[dict], tools: bool = True) -> dict:
        """Call local Ollama instance."""
        import urllib.request
        import urllib.error

        settings = get_settings().agent
        url = f"{settings.mechanic_ollama_url}/api/chat"

        payload = {
            "model": settings.mechanic_ollama_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.4},
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                response_data = json.loads(resp.read().decode("utf-8"))
                msg = response_data.get("message", {})
                return {"content": msg.get("content", "")}
        except urllib.error.URLError:
            return {"content": "[Ollama not reachable. Is it running?]"}

    # ------------------------------------------------------------------
    # Fallback (no LLM available)
    # ------------------------------------------------------------------

    def _fallback_response(self, user_message: str) -> str:
        """
        Generate a helpful response without an LLM.
        Uses the symptom parser and trouble code database for basic help.
        """
        from core.symptom_parser import parse_symptoms

        lines = []
        lines.append(
            "I'm currently running in offline mode (no LLM configured), "
            "but I can still help with basic diagnostics.\n"
        )

        # Try to parse the user's message as symptoms
        parsed = parse_symptoms(user_message)

        if parsed.matched_keywords:
            lines.append(
                f"**Detected symptoms:** {', '.join(parsed.matched_keywords)}"
            )

            if parsed.context.noise_character != "unknown":
                lines.append(
                    f"**Noise type:** {parsed.context.noise_character.replace('_', ' ').title()}"
                )

            if parsed.class_hints:
                sorted_hints = sorted(
                    parsed.class_hints.items(), key=lambda x: x[1], reverse=True
                )
                top_hint = sorted_hints[0]
                from core.diagnostic_engine import CLASS_DISPLAY_NAMES
                display = CLASS_DISPLAY_NAMES.get(top_hint[0], top_hint[0])
                lines.append(
                    f"\n**Most likely category:** {display}"
                )

            if parsed.suggested_codes:
                code_str = ", ".join(parsed.suggested_codes)
                lines.append(
                    f"**Related trouble codes to check:** {code_str}"
                )

            if parsed.location_hints:
                lines.append(
                    f"**Location:** {', '.join(parsed.location_hints)}"
                )

        # Check for trouble code mentions
        import re
        code_pattern = re.compile(r"\b[PBCU][0-9A-Fa-f]{4}\b", re.IGNORECASE)
        found_codes = code_pattern.findall(user_message)

        if found_codes and self.db_manager:
            lines.append("\n**Trouble Code Info:**")
            from database.trouble_code_lookup import lookup_codes
            definitions = lookup_codes(found_codes, self.db_manager)
            for defn in definitions:
                lines.append(
                    f"- **{defn.code}**: {defn.description} "
                    f"(Severity: {defn.severity})"
                )
                if defn.symptoms:
                    lines.append(
                        f"  Common symptoms: {', '.join(defn.symptoms)}"
                    )

        if self._diagnosis_result:
            from core.diagnostic_engine import CLASS_DISPLAY_NAMES
            result = self._diagnosis_result
            top_display = CLASS_DISPLAY_NAMES.get(
                result.top_class, result.top_class
            )
            lines.append(
                f"\n**Audio Analysis Result:** {top_display} "
                f"({result.confidence} confidence)"
            )

        lines.append(
            "\n*For a full conversational experience, configure an LLM "
            "provider (OpenAI, Anthropic, or Ollama) in your environment.*"
        )

        response = "\n".join(lines)
        self.memory.add(Message(role="assistant", content=response))
        return response
