import hashlib
import json
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12] if text else "NONE"


class AaltoExperimentResponsesClient:
    """
    Experiment-only client for Aalto Responses API models such as GPT-5.1.
    """

    def __init__(
        self,
        model_name: str | None = None,
        debug: bool = False,
    ) -> None:
        self.debug = debug

        project_root = Path(__file__).resolve().parents[2]
        env_path = Path(
            os.getenv("NLTL_ENV_FILE")
            or project_root.parent.parent / "env" / "NLTL_v2.env"
        )
        load_dotenv(env_path, override=True)

        self.api_key = (os.getenv("AALTO_API_KEY") or "").strip().strip('"').strip("'")
        self.base_url = (
            os.getenv("AALTO_RESPONSES_BASE_URL")
            or "https://aalto-openai-apigw.azure-api.net/v1/openai/responses"
        ).strip().strip('"').strip("'")
        self.default_model = (os.getenv("AALTO_MODEL") or "gpt-5.1-2025-11-13").strip()
        self.model = (model_name or self.default_model).strip()
        self.timeout = int((os.getenv("AALTO_TIMEOUT") or "120").strip())

        if not self.api_key:
            raise ValueError(f"Missing AALTO_API_KEY in {env_path}")
        if not self.base_url:
            raise ValueError(f"Missing AALTO_RESPONSES_BASE_URL in {env_path}")

        if self.debug:
            print("[DEBUG] responses base_url:", self.base_url)
            print("[DEBUG] selected_model:", self.model)
            print("[DEBUG] key length:", len(self.api_key))
            print("[DEBUG] key fingerprint:", fp(self.api_key))

    def _try_post(self, headers: dict[str, str], payload: dict[str, Any]) -> requests.Response:
        return requests.post(
            self.base_url,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )

    def _extract_text(self, data: dict[str, Any]) -> str:
        # Best case: Responses API provides output_text directly
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        # Fallback: walk the structured output content
        texts: list[str] = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text)

        if texts:
            return "\n".join(texts)

        raise RuntimeError(f"Could not extract text from Responses API payload: {json.dumps(data)[:1000]}")

    def _post(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "developer",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
        }

        header_options = [
            {
                "Content-Type": "application/json",
                "Ocp-Apim-Subscription-Key": self.api_key,
            },
            {
                "Content-Type": "application/json",
                "api-key": self.api_key,
            },
        ]

        last_response: requests.Response | None = None

        for i, headers in enumerate(header_options, start=1):
            if self.debug:
                print(f"[DEBUG] trying header option {i}: {list(headers.keys())}")

            response = self._try_post(headers, payload)

            if self.debug:
                print(f"[DEBUG] status {i}:", response.status_code)
                print(f"[DEBUG] body {i}:", response.text[:1000])

            last_response = response

            if response.status_code == 200:
                data = response.json()
                return self._extract_text(data)

        if last_response is not None and last_response.status_code in (401, 403):
            raise RuntimeError(
                f"Aalto Responses API error {last_response.status_code}: {last_response.text}\n"
                "Check if you're connected to Aalto VPN too."
            )

        raise RuntimeError(
            f"Aalto Responses API failed. Last status: {last_response.status_code if last_response else 'NO_RESPONSE'}"
        )

    def call_generator_llm(
        self,
        generator_instructions: str,
        regulation_json: dict,
        fewshot_examples: list[dict],
        repair_feedback: str = "",
        ship_graph_path: str | Path = "",
    ) -> str:
        ship_graph_text = "NONE"
        if ship_graph_path:
            try:
                ship_graph_text = Path(ship_graph_path).read_text(encoding="utf-8")
            except Exception as exc:
                ship_graph_text = f"FAILED_TO_READ_SHIP_GRAPH: {exc}"

        user_prompt = (
            f"Target regulation JSON:\n{json.dumps(regulation_json, indent=2, ensure_ascii=False)}\n\n"
            f"Ship graph path:\n{ship_graph_path or 'NONE'}\n\n"
            f"Ship graph Turtle:\n{ship_graph_text}\n\n"
            f"Relevant few-shot examples:\n{json.dumps(fewshot_examples, indent=2, ensure_ascii=False)}\n\n"
            f"Repair feedback from previous iteration:\n{repair_feedback or 'NONE'}\n"
        )
        return self._post(generator_instructions, user_prompt)

    def call_validator_llm(
        self,
        validator_instructions: str,
        regulation_json: dict,
        generated_shacl: str,
        syntax_result: dict,
        validation_result: dict,
        ship_graph_path: str = "",
        fewshot_examples: list[dict] | None = None,
    ) -> str:
        fewshot_examples = fewshot_examples or []

        ship_graph_text = "NONE"
        if ship_graph_path:
            try:
                ship_graph_text = Path(ship_graph_path).read_text(encoding="utf-8")
            except Exception as exc:
                ship_graph_text = f"FAILED_TO_READ_SHIP_GRAPH: {exc}"

        user_prompt = (
            f"Target regulation JSON:\n{json.dumps(regulation_json, indent=2, ensure_ascii=False)}\n\n"
            f"Generated SHACL:\n{generated_shacl}\n\n"
            f"Syntax result:\n{json.dumps(syntax_result, indent=2, ensure_ascii=False)}\n\n"
            f"Ship graph validation result:\n{json.dumps(validation_result, indent=2, ensure_ascii=False)}\n\n"
            f"Ship graph path:\n{ship_graph_path or 'NONE'}\n\n"
            f"Ship graph Turtle:\n{ship_graph_text}\n\n"
            f"Relevant few-shot examples:\n{json.dumps(fewshot_examples, indent=2, ensure_ascii=False)}\n\n"
            f"Important: determine the expected outcome from the regulation and ship facts, "
            f"then compare it against the actual SHACL outcome."
        )
        return self._post(validator_instructions, user_prompt)
