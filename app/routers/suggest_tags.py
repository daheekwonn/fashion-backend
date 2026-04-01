import os
import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

PROMPT = """You are tagging runway looks for a fashion trend intelligence platform.
Analyse this runway image carefully and return specific, descriptive fashion tags.

Good examples of tag style: "croc effect leather", "strong shoulder", "waxed denim", "wide-leg trouser", "pumps", "long scarf", "leather gloves", "grey denim", "brown handbag", "mini skirt", "denim set"

Tags should cover: silhouette details, key garments, fabric/texture/finish, colour, accessories, construction details.
- Be specific and descriptive, not vague ("croc effect leather" not just "leather")
- All lowercase
- 6-10 tags total

Return ONLY a comma-separated list of tags. No explanation, no preamble."""


class SuggestTagsRequest(BaseModel):
    image_url: str


@router.post("/api/looks/suggest-tags")
async def suggest_tags(body: SuggestTagsRequest):
    if not body.image_url:
        raise HTTPException(status_code=400, detail="image_url required")

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "url", "url": body.image_url},
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }],
        )

        text = message.content[0].text if message.content else ""
        tags = [
            t.strip().lower().strip('"').strip("'")
            for t in text.split(",")
            if t.strip() and len(t.strip()) < 60
        ]

        return {"tags": tags}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
