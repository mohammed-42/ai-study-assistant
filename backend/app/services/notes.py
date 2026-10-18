"""Notes generation service — grounded in document chunks via Gemini."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from uuid import UUID

import google.generativeai as genai

from app.core.config import settings
from app.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)

_NOTE_PROMPTS = {
    "summary": """\
You are a study assistant. Create a concise but thorough summary of the following study materials.
Include the main ideas, key arguments, and how they connect.
Write in clear student-friendly language. Do not invent information not present in the text.

MATERIALS:
{references}

Return JSON:
{{"summary": "your summary here"}}""",
    "key_concepts": """\
You are a study assistant. Extract the key concepts, definitions, and important facts from the following materials.
Present them as a structured list. Do not invent information not present in the text.

MATERIALS:
{references}

Return JSON:
{{"concepts": ["concept 1", "concept 2", ...]}}""",
    "definitions": """\
You are a study assistant. Extract all definitions and key terminology from the following materials.
For each term provide: the term, its definition, and a brief example if helpful.
Do not invent information not present in the text.

MATERIALS:
{references}

Return JSON:
{{"definitions": [{{"term": "...", "definition": "...", "example": "..."}}]}}""",
    "revision": """\
You are a study assistant. Create a revision-ready study note from the following materials.
Include: key points, mnemonics or memory aids if useful, common misconceptions to avoid,
and a quick self-test section with 3-5 questions and answers.
Do not invent information not present in the text.

MATERIALS:
{references}

Return JSON:
{{"note": "your revision note here", "self_test": [{{"question": "...", "answer": "..."}}]}}""",
}


async def generate_notes(
    chunks: list[DocumentChunk],
    note_type: str,
) -> str:
    """Generate notes from document chunks using Gemini.

    Args:
        chunks: Document chunks to base notes on
        note_type: One of 'summary', 'key_concepts', 'definitions', 'revision'

    Returns:
        Generated note content as a string
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key or api_key == "your-gemini-api-key":
        raise RuntimeError("GEMINI_API_KEY is not configured")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    if not chunks:
        return f"No materials available to generate {note_type} notes."

    # Build reference text from chunks
    references = []
    for chunk in chunks:
        references.append(f"[Chunk {chunk.id}]\n{chunk.content}")

    prompt_template = _NOTE_PROMPTS.get(note_type, _NOTE_PROMPTS["summary"])
    prompt = prompt_template.format(references="\n---\n".join(references))

    try:
        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
            generation_config={"temperature": 0.2, "response_mime_type": "application/json"},
        )

        text = response.text.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Fallback: return raw text
            logger.warning("Notes generation returned non-JSON: %s", text[:200])
            return text

        # Extract content based on note type
        if note_type == "summary":
            return data.get("summary", text)
        elif note_type == "key_concepts":
            concepts = data.get("concepts", [])
            if isinstance(concepts, list):
                return "\n".join(f"- {c}" for c in concepts)
            return text
        elif note_type == "definitions":
            defs = data.get("definitions", [])
            if isinstance(defs, list):
                lines = []
                for d in defs:
                    if isinstance(d, dict):
                        lines.append(f"**{d.get('term', '')}**: {d.get('definition', '')}")
                        if d.get("example"):
                            lines.append(f"  Example: {d['example']}")
                    else:
                        lines.append(f"- {d}")
                return "\n".join(lines)
            return text
        elif note_type == "revision":
            note = data.get("note", "")
            self_test = data.get("self_test", [])
            parts = [note]
            if self_test:
                parts.append("\n\n## Self-Test\n")
                for st in self_test:
                    if isinstance(st, dict):
                        parts.append(f"**Q:** {st.get('question', '')}\n**A:** {st.get('answer', '')}\n")
                    else:
                        parts.append(f"- {st}")
            return "\n".join(parts)
        return text

    except Exception as exc:
        logger.error("Notes generation failed: %s", exc)
        raise RuntimeError(f"Notes generation failed: {exc}")
