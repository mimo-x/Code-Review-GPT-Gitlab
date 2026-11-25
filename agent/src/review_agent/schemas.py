"""Tool schemas as sent to the model: OpenAI function-calling entries built from pydantic
argument models."""

from __future__ import annotations


def compact_schema(schema: dict) -> dict:
    """Plain JSON schema for function calling: $refs inlined, no per-field titles, optional
    fields as their plain type. Smaller (it is sent on every call) and easier for small
    models and server-side tool parsers than pydantic's raw output."""
    definitions = schema.get("$defs", {})

    def walk(value):
        if isinstance(value, list):
            return [walk(item) for item in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            return walk(definitions[value["$ref"].rsplit("/", 1)[-1]])
        options = value.get("anyOf")
        if options and len(options) == 2 and {"type": "null"} in options:
            plain = next(option for option in options if option != {"type": "null"})
            rest = {k: v for k, v in value.items() if k not in {"anyOf", "default"}}
            return walk({**plain, **rest})
        return {
            key: walk(item)
            for key, item in value.items()
            if key != "$defs"
            and not (key == "title" and isinstance(item, str))
            and not (key == "default" and item is None)
        }

    return walk(schema)


def tool_schema(name: str, model, description: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": compact_schema(model.model_json_schema()),
        },
    }
