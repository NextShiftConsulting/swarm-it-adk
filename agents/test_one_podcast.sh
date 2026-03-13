#!/bin/bash
# Quick test: Generate dialogue version for RSN Collapse post

# Default provider: mimo (Xiaomi cloud API - cost-effective)
# Alternative: xiami (local Ollama - free but requires setup)
PROVIDER=${1:-mimo}

echo "[*] Testing MIMO Agent on RSN Collapse post..."
echo "    Provider: $PROVIDER"
echo ""

# Find the blog post
BLOG_DIR="/c/Users/marti/github/nsc-main-gatsby/src/content/blog"
POST_SLUG="rsn-collapse-when-decomposition-fails"
OUTPUT_DIR="./test_output"

mkdir -p "$OUTPUT_DIR"

# Find the MDX file
BLOG_FILE=$(find "$BLOG_DIR" -name "*${POST_SLUG}*" -type f | head -1)

if [ -z "$BLOG_FILE" ]; then
    echo "[-] Blog post not found: $POST_SLUG"
    exit 1
fi

echo "[+] Found blog post: $BLOG_FILE"
echo ""

# Check credentials based on provider
if [ "$PROVIDER" = "mimo" ]; then
    if [ -z "$SWARM_MIMO_API_KEY" ]; then
        echo "[-] Error: SWARM_MIMO_API_KEY not set"
        echo ""
        echo "Set MiMo credentials:"
        echo "  export SWARM_MIMO_API_KEY=mimo_xxxxxxxxxxxxxxxx"
        echo "  export SWARM_MIMO_ENDPOINT=https://api.mimo.xiaomi.com/v1"
        echo "  export SWARM_MIMO_MODEL=mimo-v2-flash"
        echo ""
        echo "Or use local Ollama instead:"
        echo "  bash test_one_podcast.sh xiami"
        exit 1
    fi
    echo "[*] Using Xiaomi MiMo cloud API"
    echo "    Endpoint: ${SWARM_MIMO_ENDPOINT:-https://api.mimo.xiaomi.com/v1}"
    echo "    Model: ${SWARM_MIMO_MODEL:-mimo-v2-flash}"
elif [ "$PROVIDER" = "xiami" ]; then
    echo "[*] Using local Ollama"
    echo "    Endpoint: ${SWARM_XIAMI_ENDPOINT:-http://localhost:11434/api/generate}"
    echo "    Model: ${SWARM_XIAMI_MODEL:-llama2}"
fi

echo ""
echo "[*] Generating dialogue version..."
echo "    This will take 30-60 seconds..."
echo ""

# Run MIMO agent
python podcast_mimo.py \
    --provider "$PROVIDER" \
    --blog-post "$BLOG_FILE" \
    --output "$OUTPUT_DIR/${POST_SLUG}_dialogue.mp3"

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 SUCCESS!"
    echo ""
    echo "Now compare:"
    echo "  Narration (old): https://dsai-2025-asu.s3.amazonaws.com/audio/${POST_SLUG}.mp3"
    echo "  Dialogue (new):  $OUTPUT_DIR/${POST_SLUG}_dialogue.mp3"
    echo ""
    echo "Play the dialogue version:"
    echo "  start $OUTPUT_DIR/${POST_SLUG}_dialogue.mp3"
else
    echo ""
    echo "❌ Generation failed. Check errors above."
    exit 1
fi
