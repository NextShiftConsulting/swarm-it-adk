#!/bin/bash
# Quick test: Generate dialogue version for RSN Collapse post

echo "🧪 Testing MIMO Agent on RSN Collapse post..."
echo ""

# Find the blog post
BLOG_DIR="/c/Users/marti/github/nsc-main-gatsby/src/content/blog"
POST_SLUG="rsn-collapse-when-decomposition-fails"
OUTPUT_DIR="./test_output"

mkdir -p "$OUTPUT_DIR"

# Find the MDX file
BLOG_FILE=$(find "$BLOG_DIR" -name "*${POST_SLUG}*" -type f | head -1)

if [ -z "$BLOG_FILE" ]; then
    echo "❌ Blog post not found: $POST_SLUG"
    exit 1
fi

echo "✅ Found blog post: $BLOG_FILE"
echo ""
echo "🎬 Generating dialogue version..."
echo "   This will take 30-60 seconds..."
echo ""

# Run MIMO agent
python podcast_mimo.py \
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
