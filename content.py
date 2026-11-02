"""Idea + caption generation and image quality control (Anthropic API)."""
import base64
import json
import re

from config import PERSONA, QC_MODEL, TEXT_MODEL


def _client():
    import anthropic
    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY


def _json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"No JSON in model reply: {text[:200]}")
    return json.loads(m.group(0))


def _system():
    p = PERSONA
    name = f" named {p['name']}" if p.get("name") else ""
    return f"""You plan and write posts for an Instagram page run by a fictional adult persona: a {p['age']}-year-old young woman{name}.
Interests: {', '.join(p['interests'])}.
Voice: {p['tone']}. Caption language: {p['language']}.
Look of the page: {p['visual_style']}.
Her appearance (only when she is in frame): {p['appearance']}.
Never produce: {'; '.join(p['avoid'])}.
Everything must be safe for work. When she appears she is clearly an adult, fully clothed in everyday outfits.
Vary topics, places and moods; never repeat a recent idea.
Captions: 1-3 short sentences, sometimes ending with a light question; no hashtags inside the caption.
Reply with a single JSON object and nothing else."""


def new_idea(recent, n_tags=8):
    user = (
        "Recent posts (do not repeat):\n- " + "\n- ".join(recent or ["(none yet)"]) + "\n\n"
        "Create the next post. JSON keys: topic (short), persona_in_frame (bool), "
        "image_prompt (English, photographic, max 80 words, no text/logos in the image), "
        f"caption, hashtags (list of {n_tags} relevant tags), alt_text (one factual sentence)."
    )
    r = _client().messages.create(
        model=TEXT_MODEL, max_tokens=900, system=_system(),
        messages=[{"role": "user", "content": user}],
    )
    return _json(r.content[0].text)


def review(image_path, idea):
    """Vision QC. Returns {'score': 1-10, 'safe': bool, 'issues': [...]}."""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    prompt = (
        f"Brief for this AI-generated Instagram image: {idea['image_prompt']}\n"
        "Rate 1-10 for: anatomy (hands, faces, limbs), realism, visual appeal, match to brief, "
        "and absence of visible text, logos or watermarks. Set safe=false if the image is sexualized "
        "or revealing, shows violence, a real brand, or a subject who looks younger than 18. "
        'Reply with JSON only: {"score": number, "safe": boolean, "issues": [strings]}'
    )
    r = _client().messages.create(
        model=QC_MODEL, max_tokens=300,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
            {"type": "text", "text": prompt},
        ]}],
    )
    return _json(r.content[0].text)
