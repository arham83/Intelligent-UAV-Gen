from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from openai import OpenAI
import os
import csv
from datetime import datetime

load_dotenv(override=True)

SUCCESS_STATES = {"completed", "succeeded"}

class Bot:
    def __init__(self, logger, system_prompt, log_path: str = "logs/assistant_tokens.csv"):
        self.logger = logger
        self.client = OpenAI()
        self.model: str = os.getenv("MODEL_NAME", "gpt-4o-mini") 
        self.name = "UAV Test Generator"
        self.assistant = self.initialize_bot(system_prompt)

        # token accounting
        self.cumulative_tokens = 0
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        if not os.path.exists(self.log_path):
            with open(self.log_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp",
                    "thread_id",
                    "run_id",
                    "user_prompt",
                    "assistant_reply",
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                    "cumulative_tokens"
                ])

    def initialize_bot(self, system_prompt) -> Dict[str, Any]:
        """Create and return an Assistant object (as a dict)."""
        return self.client.beta.assistants.create(
            name=self.name,
            model=self.model,
            tools=[{"type": "file_search"}],
            instructions=system_prompt,
        )

    def upload_file(self, file_path: Optional[Path]) -> Optional[str]:
        """Optionally upload a file (e.g., HTML) for file_search. Returns file_id or None."""
        if file_path is None:
            self.logger.debug("No file path provided; skipping file upload.")
            return None
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        f = self.client.files.create(file=file_path, purpose="assistants")
        file_id = f.id
        self.logger.info(f"Uploaded file ID: {file_id}")
        return file_id

    def upload_image(self, img_path: Optional[Path]) -> Optional[str]:
        """Optionally upload an image file for vision. Returns file_id or None."""
        if img_path is None:
            self.logger.debug("No image path provided; skipping image upload.")
            return None
        if not img_path.exists():
            raise FileNotFoundError(f"Image file not found: {img_path}")
        img_file = self.client.files.create(file=img_path, purpose="vision")
        file_id = img_file.id
        self.logger.info(f"Uploaded image file ID: {file_id}")
        return file_id

    def create_thread(self) -> Dict[str, Any]:
        """Create an empty thread (no messages yet)."""
        thread = self.client.beta.threads.create()
        self.logger.info(f"Thread created: {getattr(thread, 'id', thread)}")
        return thread

    def post_message_to_thread(
        self,
        thread_id: str,
        *,
        prompt_text: Optional[str] = None,
        file_id: Optional[str] = None,
        image_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Append a user message, run the assistant, then return a dict with reply + usage."""
        self.logger.info("Building the prompt.....")
        attachments: List[Dict[str, Any]] = []
        if file_id:
            attachments.append({"file_id": file_id, "tools": [{"type": "file_search"}]})

        # Message content
        content: List[Dict[str, Any]] = []
        if prompt_text:
            content.append({"type": "text", "text": prompt_text})
        if image_id:
            content.append({"type": "image_file", "image_file": {"file_id": image_id}})

        kwargs: Dict[str, Any] = dict(thread_id=thread_id, role="user", content=content)
        if attachments:
            kwargs["attachments"] = attachments

        msg = self.client.beta.threads.messages.create(**kwargs)
        self.logger.info(f"User message created: {getattr(msg, 'id', msg)}")

        # Start run and wait; capture run (for usage)
        run = self.run_and_wait(thread_id=thread_id, assistant_id=self.assistant.id)

        # Fetch the assistant reply
        reply_text = self.fetch_reply(thread_id) or ""

        # Extract token usage (if present)
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        run_id = getattr(run, "id", None)

        usage = getattr(run, "usage", None)
        # Newer SDKs expose usage as an object; fallback to dict keys if needed
        if usage:
            prompt_tokens = getattr(usage, "prompt_tokens", getattr(usage, "input_tokens", 0)) or 0
            completion_tokens = getattr(usage, "completion_tokens", getattr(usage, "output_tokens", 0)) or 0
            # Some SDKs expose total_tokens directly; otherwise sum
            total_tokens = getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0

        self.cumulative_tokens += total_tokens

        # Log to CSV
        with open(self.log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.utcnow().isoformat(),
                thread_id,
                run_id,
                (prompt_text or ""),
                reply_text,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                self.cumulative_tokens,
            ])

        self.logger.info(
            f"[Tokens] prompt={prompt_tokens}, completion={completion_tokens}, "
            f"total={total_tokens}, cumulative={self.cumulative_tokens}"
        )

        return {
            "reply": reply_text,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cumulative_tokens": self.cumulative_tokens,
            },
            "thread_id": thread_id,
            "run_id": run_id,
        }

    def run_and_wait(self, thread_id: str, assistant_id: str) -> Dict[str, Any]:
        """Start a Run and block until it reaches a terminal state. Return the Run object."""
        run = self.client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=assistant_id,
        )

        status = getattr(run, "status", None)
        if status not in SUCCESS_STATES:
            err = getattr(run, "last_error", None)
            details = None
            if err:
                if isinstance(err, dict):
                    details = f"code={err.get('code')} message={err.get('message')}"
                else:
                    details = str(err)
            self.logger.error(f"Run did not complete successfully. status={status} details={details}")
            raise RuntimeError(
                f"Run did not complete successfully. status={status} details={details}"
            )

        return run

    def fetch_reply(self, thread_id: str) -> Optional[str]:
        """Return the first plain-text assistant reply in the thread (no new run)."""
        msgs = self.client.beta.threads.messages.list(thread_id=thread_id)
        for m in getattr(msgs, "data", []) or []:
            if getattr(m, "role", None) != "assistant":
                continue
            for part in getattr(m, "content", []) or []:
                if getattr(part, "type", None) == "text" and getattr(part, "text", None):
                    v = getattr(part.text, "value", None)
                    if v:
                        return v
        return None
