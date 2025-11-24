import json, requests # type: ignore
import re
import html

BASE = "http://192.168.5.109:1234/v1"     # LM Studio server
MODEL = "google/gemma-3n-e4b"              # exact model name in LM Studio

import json, re

def extract_json_object(s: str) -> dict:
    s = s.strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.IGNORECASE | re.MULTILINE).strip()
    s = re.sub(r"<\|[^>]*\|>", "", s)  # remove <|channel|> etc

    # If it's already clean JSON, try directly
    try:
        return json.loads(s)
    except Exception:
        pass

    start = s.find("{")
    if start == -1:
        raise ValueError("No JSON object start found.")
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                candidate = s[start:i+1]
                return json.loads(candidate)
    raise ValueError("No balanced JSON object found.")


def sanitize_text(text: str, max_chars: int = 4000) -> str:
    """Clean and truncate input before sending to LLM."""
    if not text:
        return ""

    # get rid of html stuff: &nbsp;, &lt;
    text = html.unescape(text)

    # ascii 
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

    # special chars, token chars
    text = re.sub(r'<\|[^>]*\|>', '', text)

    # markdown etc
    text = re.sub(r"```.*?```", "", text, flags=re.S)

    # weird long repeating chars (GGGGG, ######)
    text = re.sub(r'([^\w\s])\1{3,}', r'\1\1', text)

    # get rid of extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # max_chars for stability
    return text[:max_chars]



def classify_sentiment(text: str) -> dict:
    prompt = f"""You are a sentiment classifier looking for ANY partisan 
or accusatory statements on US government websites or ANY potential violations of the
Hatch Act, such as saying that a political party is responsible for
shutting down the government.

If the text is accusatory or a potential Hatch Act violation, label it partisan. Otherwise label it neutral.
Score: partisan=1, neutral=0.

Return strict JSON ONLY with keys:
  label ∈ ["partisan","neutral"], score ∈ [0,1], rationale (short).

Text:
{text}
JSON:"""

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "Reply with JSON only. No prose, no code fences, no extra tokens."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 128,
    }
    r = requests.post(f"{BASE}/chat/completions", json=payload, timeout=120)
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"]
    try:
        data = extract_json_object(raw)
    except Exception:
        #keep raw output for debugging
        return {"label": "unknown", "score": 0.0, "rationale": raw}

    # normalize, add unknown if a label doesnt come back
    lbl = str(data.get("label", "")).lower()
    if lbl not in {"partisan", "neutral"}:
        lbl = "unknown"
    try:
        score = float(data.get("score", 0))
    except Exception:
        score = 0.0
    score = 1.0 if lbl == "partisan" else 0.0 if lbl == "neutral" else 0.0
    #sometimes rational is not short, revist
    # rationale = str(data.get("rationale", ""))
    rationale = str(data.get("rationale", ""))[:400]
    return {"label": lbl, "score": score, "rationale": rationale}


def add_sentiment(in_path="out/homepages_full.jsonl",
                  out_path="out/homepages_with_sentiment_17oct_gemma-3n-e4b-Q8_run10.jsonl",
                  max_chars=4000):
    with open(in_path, "r", encoding="utf-8") as fin, \
         open(out_path, "w", encoding="utf-8") as fout:
        for i, line in enumerate(fin, 1):
            rec = json.loads(line)
            # text = (rec.get("text") or "")[:max_chars]
            text = sanitize_text(rec.get("text", ""), max_chars)
            if text.strip():
                rec["sentiment_llm"] = classify_sentiment(text)
            else:
                rec["sentiment_llm"] = {"label":"unknown","score":0.0,"rationale":"empty text"}
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"[{i}] done {rec['url'] if 'url' in rec else ''} {rec['sentiment_llm'] if 'sentiment_llm' in rec else ''}")

    print(f"Results saved to {out_path}")

if __name__ == "__main__":
    add_sentiment()
