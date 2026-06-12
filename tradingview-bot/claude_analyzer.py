"""Claude AI analyzer for TradingView signals using tool use."""
import json
import logging
from typing import Any

import anthropic

import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions exposed to Claude
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "name": "execute_trade",
        "description": (
            "Execute a trade decision based on the analyzed signal. "
            "Call this tool once you have assessed the signal and decided on an action."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["buy", "sell", "hold"],
                    "description": "Trading action to take.",
                },
                "size_pct": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "description": (
                        "Percentage of available balance to use for this trade (0-100). "
                        "Use 0 when action is 'hold'."
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": "Concise reasoning for the decision (max 200 chars).",
                },
            },
            "required": ["action", "size_pct", "reason"],
        },
    }
]

SYSTEM_PROMPT = """You are a professional crypto trading assistant integrated into an automated trading system.

You will receive a TradingView alert signal with market data and technical indicators.
Your job is to analyze the signal and use the `execute_trade` tool to record your decision.

Guidelines:
- Be conservative: prefer smaller position sizes when uncertain.
- Always call `execute_trade` — never skip it.
- Keep your reasoning concise and factual.
- Consider RSI overbought (>70) / oversold (<30) levels.
- Confirm EMA crossover direction before acting.
- When the signal action is 'buy'/'sell' but conditions look unfavorable, prefer 'hold'.
"""


class TradeDecision:
    """Structured result from Claude's analysis."""

    def __init__(self, action: str, size_pct: float, reason: str) -> None:
        self.action = action  # buy | sell | hold
        self.size_pct = max(0.0, min(100.0, float(size_pct)))
        self.reason = reason

    def __repr__(self) -> str:
        return f"TradeDecision(action={self.action!r}, size_pct={self.size_pct}, reason={self.reason!r})"

    def to_dict(self) -> dict:
        return {"action": self.action, "size_pct": self.size_pct, "reason": self.reason}


class ClaudeAnalyzer:
    """Analyze TradingView signals using Claude with tool use."""

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def _build_user_message(self, signal: dict[str, Any]) -> str:
        indicators = signal.get("indicators", {})
        lines = [
            f"Symbol: {signal.get('symbol', 'N/A')}",
            f"Action suggested by alert: {signal.get('action', 'N/A')}",
            f"Current price: {signal.get('price', 'N/A')}",
            f"Timeframe: {signal.get('interval', 'N/A')}",
            f"Alert message: {signal.get('message', '')}",
        ]
        if indicators:
            lines.append("Technical indicators:")
            for k, v in indicators.items():
                lines.append(f"  {k}: {v}")
        lines.append(
            "\nPlease analyze this signal and call the `execute_trade` tool with your decision."
        )
        return "\n".join(lines)

    def analyze(self, signal: dict[str, Any]) -> TradeDecision:
        """
        Send signal to Claude and return a TradeDecision.
        Uses tool use (synchronous) — wraps cleanly for async callers via run_in_executor.
        """
        user_message = self._build_user_message(signal)
        logger.info("Sending signal to Claude for analysis: %s", signal.get("symbol"))

        response = self._client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            tool_choice={"type": "auto"},
            messages=[{"role": "user", "content": user_message}],
        )

        logger.debug("Claude stop_reason: %s", response.stop_reason)

        # Extract the tool call
        for block in response.content:
            if block.type == "tool_use" and block.name == "execute_trade":
                inp = block.input
                decision = TradeDecision(
                    action=inp["action"],
                    size_pct=inp["size_pct"],
                    reason=inp["reason"],
                )
                logger.info("Claude decision: %s", decision)
                return decision

        # Fallback: Claude didn't call the tool — hold conservatively
        logger.warning("Claude did not call execute_trade, defaulting to hold")
        return TradeDecision(
            action="hold",
            size_pct=0,
            reason="Claude did not provide a structured decision; defaulting to hold.",
        )
