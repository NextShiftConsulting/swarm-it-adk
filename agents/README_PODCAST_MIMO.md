# MIMO Podcast Agent - Natural Dialogue Generation

Transform single-voice blog narration into natural multi-speaker dialogue podcasts.

## Quick Start

### Test with One Post

```bash
cd /c/Users/marti/github/swarm-it-adk/agents

# Quick test with RSN Collapse post
bash test_one_podcast.sh
```

This generates a dialogue version of "RSN Collapse" that you can compare against the narration version.

### Regenerate All 10 Posts

```bash
# Install dependencies first
pip install anthropic boto3 pydub

# Set API key
export ANTHROPIC_API_KEY=your-key-here

# Batch regenerate all 10 posts
python batch_regenerate_podcasts.py \
    --blog-dir /c/Users/marti/github/nsc-main-gatsby/src/content/blog \
    --output-dir ./dialogue_output
```

This will generate dialogue versions for all 10 posts listed.

## What It Does

### Before (Narration)
```
🤖 Single voice reads blog post:
"RSN collapse is when Relevant, Superfluous, and Noise categories
become indistinguishable, leading to measurement breakdown..."
```

**Problems:**
- Mechanical, robotic delivery
- Hard to follow complex concepts
- No engagement or pacing
- Listener attention drops

### After (Dialogue)
```
🎙️  Host + Expert conversation:

HOST: "So Rudy, what happens when your quality metrics stop working?"

EXPERT: "Great question! Imagine your email spam filter suddenly
         can't tell important messages from junk. That's RSN collapse."

HOST: "So the measurement itself breaks down? Like you need a
       quality check for the quality check?"

EXPERT: "Exactly! It's the classic 'who watches the watchers' problem.
         When RSN collapse happens, you can't measure whether your
         AI system is working correctly..."
```

**Benefits:**
- Natural, engaging conversation
- Host asks questions listeners would ask
- Expert explains with analogies
- Much higher completion rates

## How It Works

### Multi-Agent Pipeline

```
Blog Post (.mdx)
    ↓
Producer Agent (creates dialogue outline)
    ↓
Host Agent + Expert Agent (generate dialogue)
    ↓
Quality Agent (RSCT validation)
    ↓
AWS Polly (text-to-speech, 2 voices)
    ↓
Audio Mixer (combine segments)
    ↓
Final Dialogue Podcast (.mp3)
```

### Quality Gates (RSCT)

Every dialogue is validated:

- **R >= 0.7**: Covers at least 70% of blog concepts
- **S <= 0.3**: No more than 30% filler content
- **N <= 0.1**: Less than 10% factual errors
- **kappa >= 0.8**: Overall quality score

If quality gates fail, dialogue is rejected and you get the original narration.

## Output Files

For each post, you get:

1. **Audio**: `{slug}_dialogue.mp3` - Final podcast with dialogue
2. **Script**: `{slug}_dialogue_script.json` - Full dialogue transcript
3. **Certificate**: RSCT quality scores included in script JSON

## Comparing Versions

After generation, you can A/B test:

```bash
# Original narration (S3)
https://dsai-2025-asu.s3.amazonaws.com/audio/rsn-collapse-when-decomposition-fails.mp3

# New dialogue (local)
./dialogue_output/rsn-collapse-when-decomposition-fails_dialogue.mp3
```

Listen to both and compare:
- Engagement level
- Ease of understanding
- Listener retention
- Overall quality

## Voice Configuration

Current voices:
- **Host**: Matthew (male, professional, conversational)
- **Expert**: Joanna (female, warm, authoritative)

You can change in `podcast_mimo.py`:
```python
self.voices = {
    "host": "Matthew",      # or Stephen, Joey
    "expert": "Joanna"      # or Kendra, Kimberly, Salli, Ruth
}
```

## Cost per Episode

**Dialogue Generation:**
- Claude API (4 calls): ~$0.15
- AWS Polly (2 voices): ~$0.50
- Total: ~$0.65 per episode

**vs. Original Narration:**
- AWS Polly (1 voice): ~$0.40

**Cost increase**: +$0.25 per episode (+63%)

## Expected Metrics

Based on industry benchmarks for dialogue podcasts:

| Metric | Narration | Dialogue | Lift |
|--------|-----------|----------|------|
| Completion Rate | ~40% | ~65% | +62% |
| Avg Listen Time | 3.5 min | 6.5 min | +86% |
| Engagement | Low | High | - |

## Troubleshooting

### Missing Dependencies

```bash
pip install anthropic boto3 pydub

# For audio mixing, also install ffmpeg:
# Windows: choco install ffmpeg
# Mac: brew install ffmpeg
```

### API Key Issues

```bash
# Set environment variable
export ANTHROPIC_API_KEY=sk-ant-...

# Or pass directly
python podcast_mimo.py --api-key sk-ant-... --blog-post ...
```

### Quality Gates Failing

If dialogue keeps failing quality validation:

1. Check the script JSON to see RSCT scores
2. Look for factual errors (N score)
3. Check if key concepts are missing (R score)
4. Review dialogue for excessive filler (S score)

The agent will retry with better prompts if gates fail.

### Audio Mixing Errors

If pydub/ffmpeg errors occur:

1. Install ffmpeg: `choco install ffmpeg` (Windows)
2. Restart terminal to refresh PATH
3. Try again

## Next Steps

### 1. Test Single Episode

```bash
bash test_one_podcast.sh
```

Listen to output, compare to narration.

### 2. Regenerate All 10 Posts

```bash
python batch_regenerate_podcasts.py \
    --blog-dir /c/Users/marti/github/nsc-main-gatsby/src/content/blog \
    --output-dir ./dialogue_output
```

### 3. Upload to S3 (Separate Bucket/Folder)

```bash
# Upload dialogue versions to S3
for file in dialogue_output/*_dialogue.mp3; do
    slug=$(basename "$file" _dialogue.mp3)
    aws s3 cp "$file" s3://dsai-2025-asu/audio-dialogue/${slug}.mp3
done
```

### 4. Create Separate RSS Feed

Modify `gatsby-config.mjs` to create second RSS feed:
- `https://nextshiftconsulting.com/rss.xml` (narration)
- `https://nextshiftconsulting.com/rss-dialogue.xml` (dialogue)

Let users choose which version to subscribe to.

### 5. A/B Test

Publish both feeds, track:
- Which feed gets more subscribers?
- Which has higher completion rates?
- Which gets more positive feedback?

## Files

- `podcast_mimo.py` - Main MIMO agent implementation
- `batch_regenerate_podcasts.py` - Batch processing script
- `test_one_podcast.sh` - Quick single-post test
- `README_PODCAST_MIMO.md` - This file

## Architecture Docs

Full design documentation: `docs/analysis/podcast-mimo-agent-architecture.md`

## Questions?

Check the architecture doc for detailed agent design, prompt templates, and quality gate logic.
