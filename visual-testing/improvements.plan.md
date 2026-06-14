# ui_agent.py — Improvement Ideas

## 1. Text input / multi-step ADVANCE sequences

Support typing into form fields as part of the advancement gesture.

**Format** — semicolon-separated steps on one ADVANCE line:
```
tap 50% 28%; type "user@example.com"; tap 50% 45%; type "secret123"; tap 50% 78%
```

**Storage** in `index.json`:
```json
"advance": {"gesture": "sequence", "steps": [
  {"gesture": "tap",  "x": 0.50, "y": 0.28},
  {"gesture": "type", "text": "user@example.com"},
  {"gesture": "tap",  "x": 0.50, "y": 0.45},
  {"gesture": "type", "text": "secret123"},
  {"gesture": "tap",  "x": 0.50, "y": 0.78}
]}
```

**Execution** — `type` step: `System Events keystroke "text"` (Accessibility permission already required for window bounds). Android: `adb shell input text "..."`.

**Note** — test credentials end up in `baselines/index.json` (plain text). Use throwaway credentials, not real ones. Some apps autocorrect/autocapitalize — may need a dismiss-autocorrect tap or Return keystroke after each field.

---

## 2. Tap coordinate accuracy

LLM percentage estimates can be off by ~10% (estimated 93%, actual 82%), landing in the iOS home indicator gesture area. Current mitigation: prompt instructs the LLM to tap the text center of the button label and stay above 92% Y.

**Further ideas:**
- Overlay a coordinate grid on the screenshot before sending to the LLM so it can read off positions rather than estimate them visually.
- Ask the LLM for a bounding box (`x1% y1% x2% y2%`) and derive the tap from the box center — more robust than a single-point estimate.
- During `record`, after storing a tap, perform a test-tap and take a screenshot to verify the screen changed before saving. Retry the LLM if not.

---

## 3. Tap verification during record

After the LLM stores an ADVANCE gesture, immediately execute it as a dry run and check whether the screen changed. If the screen did NOT change, ask the LLM to try again before saving the baseline.

This catches wrong coordinates at record time rather than at check time in CI.

---

## 4. Local LLM support via Ollama (cost reduction)

Cloud vision calls get expensive at scale. The stored-advance optimization already cuts calls to 1 per step on the happy path — but that's still N calls per flow per CI run.

**Vision-capable models in Ollama:**

| Model | Size | Multi-image | Strength |
|-------|------|-------------|----------|
| `llama3.2-vision:11b` | 11B | Yes | Best instruction following |
| `qwen2.5vl:7b` | 7B | Yes | Strong on UI/screenshots |
| `minicpm-v` | 8B | Yes | Good at comparison |
| `moondream` | 1.6B | No | Too small, can't compare two images |

**Task difficulty mapping:**
- LABEL / REVIEW (CAPTURE_PROMPT): easy — local models handle fine
- MATCH / MISMATCH: medium — local models reach ~80-85% accuracy vs Claude ~95%
- TAP coordinates (TAP_PROMPT): hard — spatial precision is where small models fail most

**Proposed `--vision-model` flag:**
- `claude` — current default, Anthropic API
- `local` — Ollama for everything (cheapest, slightly lower accuracy)
- `hybrid` — Ollama for MATCH/MISMATCH (frequent, cheap task), Claude only for TAP (rare, needs precision)

Hybrid is the sweet spot: MATCH runs every step on every CI run; TAP only fires on regressions.

**Implementation:** `_vision_call` gets an optional `model_override` parameter. Ollama exposes an OpenAI-compatible API with base64 image support — same pattern already used in `providers.py`.

```python
# Ollama vision call (OpenAI-compatible endpoint)
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
response = client.chat.completions.create(
    model="llama3.2-vision",
    messages=[{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        {"type": "text", "text": prompt},
    ]}],
)
```

---

## 5. Back-navigation check

The flow spec can describe back gestures (swipe left, hardware back), but `check` mode never exercises them — it only checks the forward path. A `--check-back` flag could verify that each step also supports back navigation correctly.
