from __future__ import annotations

import uuid

from agents.scriptgenerator.llm import complete_json
from agents.scriptgenerator.pipeline_log import log_event
from agents.scriptgenerator.State.scriptstate import (
    Character,
    ScriptState,
    as_dict,
    parse_project,
    parse_script,
)


async def CharacterManagerNode(state: ScriptState) -> ScriptState:
    logs = list(state.get("logs") or [])
    project = parse_project(state.get("project"))
    script = parse_script(state.get("script"))

    payload = await complete_json(
        system=(
            "Extract 1-4 on-screen characters from a video script. "
            "Return JSON {\"characters\": [{\"name\",\"description\",\"appearance\","
            "\"personality\",\"voice\"}]}."
        ),
        user=(
            f"Project: {project.name}\n"
            f"Logline: {script.logline}\n"
            f"Script:\n{script.body}"
        ),
    )

    raw = payload.get("characters") if isinstance(payload.get("characters"), list) else []
    characters: list[Character] = []
    for item in raw[:4]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        characters.append(
            Character(
                id=str(uuid.uuid4())[:8],
                name=name[:80],
                description=str(item.get("description") or "")[:400],
                appearance=str(item.get("appearance") or "")[:400],
                personality=str(item.get("personality") or "")[:200],
                voice=str(item.get("voice") or "")[:80] or None,
            )
        )

    if not characters:
        characters.append(
            Character(
                id=str(uuid.uuid4())[:8],
                name="Presenter",
                description="On-camera narrator for the video.",
                appearance="Natural, professional, well-lit.",
                personality="Clear and confident",
            )
        )

    logs.append(f"character_manager:{len(characters)}")
    log_event(
        "1_story",
        "Characters defined",
        count=len(characters),
        names=", ".join(c.name for c in characters),
    )
    return {**state, "characters": [as_dict(c) for c in characters], "logs": logs}
