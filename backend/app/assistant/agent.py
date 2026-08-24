import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentResponse:
    text: str
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None


class PiAgentClient:
    def __init__(
        self,
        *,
        provider: str,
        model: str,
        executable: str = "pi",
        timeout: float = 120.0,
        environment: dict[str, str] | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.executable = executable
        self.timeout = timeout
        self.environment = environment or {}

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
    ) -> AgentResponse:
        prompt = prompt.strip()

        if not prompt:
            raise ValueError("prompt cannot be empty")

        command = [
            self.executable,
            "--provider",
            self.provider,
            "--model",
            self.model,
            "--no-tools",
            "--no-session",
            "--mode",
            "json",
            "--print",
        ]

        if system:
            command.extend(
                [
                    "--system-prompt",
                    system,
                ]
            )

        command.append(prompt)

        process_environment = os.environ.copy()
        process_environment.update(self.environment)

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=process_environment,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )
        except TimeoutError:
            process.kill()
            await process.wait()

            raise TimeoutError(
                f"Pi agent timed out after {self.timeout:.0f}s"
            )

        if process.returncode != 0:
            error = stderr.decode("utf-8", errors="replace").strip()

            raise RuntimeError(
                f"Pi agent failed with exit code "
                f"{process.returncode}: {error}"
            )

        return self._parse_response(
            stdout.decode("utf-8", errors="replace")
        )

    def _parse_response(
        self,
        output: str,
    ) -> AgentResponse:
        final_message: dict[str, Any] | None = None

        for raw_line in output.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if event.get("type") != "message_end":
                continue

            message = event.get("message") or {}

            if message.get("role") == "assistant":
                final_message = message

        if final_message is None:
            raise ValueError(
                "Pi JSON output did not contain a final "
                "assistant message"
            )

        content = final_message.get("content") or []

        text_parts = [
            item.get("text", "")
            for item in content
            if item.get("type") == "text"
        ]

        text = "".join(text_parts).strip()

        if not text:
            raise ValueError(
                "Pi final assistant message contained no text"
            )

        usage = final_message.get("usage") or {}

        return AgentResponse(
            text=text,
            provider=str(
                final_message.get("provider") or self.provider
            ),
            model=str(
                final_message.get("model") or self.model
            ),
            input_tokens=usage.get("input"),
            output_tokens=usage.get("output"),
        )
