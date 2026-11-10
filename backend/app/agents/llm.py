import json
import logging
from typing import Any

import openai

from ..config import settings

logger = logging.getLogger(__name__)


def call_llm(prompt: str, schema_cls: type[Any]) -> Any:
    client = openai.OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.groq_api_key,
        timeout=20.0,
    )
    schema_str = json.dumps(schema_cls.model_json_schema(), ensure_ascii=False)
    system_prompt = (
        "Eres un analista y arquitecto de software senior para estimaciones de proyectos TI.\n"
        f"Tu respuesta DEBE ser exclusivamente un JSON válido que se ajuste estrictamente a este esquema:\n{schema_str}"
    )
    response = client.chat.completions.create(
        model=settings.groq_model,
        response_format={"type": "json_object"},
        temperature=0.1,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    )
    raw_text = response.choices[0].message.content or "{}"
    return schema_cls.model_validate_json(raw_text)
