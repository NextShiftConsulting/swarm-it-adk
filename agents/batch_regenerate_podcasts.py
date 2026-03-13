#!/usr/bin/env python3
"""
Batch regenerate existing narration podcasts as dialogue versions

Usage:
    python batch_regenerate_podcasts.py --blog-dir /path/to/nsc-main-gatsby/src/content/blog
"""

import argparse
import os
import sys
from pathlib import Path
from podcast_mimo import PodcastMIMOAgent
import json

# Posts to regenerate (from user's list)
TARGET_POSTS = [
    "rsn-collapse-when-decomposition-fails",
    "the-same-image-over-and-over",
    "when-models-forget-to-be-curious",
    "the-slow-poison-drift",
    "jailbreaks-and-the-ood-problem",
    "hallucination-has-structure",
    "when-sources-disagree",
    "glue-on-pizza",
    "lost-in-the-middle",
    "air-canadas-812-lesson"
]

def find_blog_post_file(blog_dir: Path, slug: str) -> Path:
    """
    Find MDX file for given slug
    """
    # Try common patterns
    patterns = [
        f"*{slug}.mdx",
        f"*{slug}*.mdx"
    ]

    for pattern in patterns:
        matches = list(blog_dir.glob(pattern))
        if matches:
            return matches[0]

    return None


def main():
    parser = argparse.ArgumentParser(description='Batch regenerate podcasts as dialogue')
    parser.add_argument('--blog-dir', required=True, help='Path to blog content directory')
    parser.add_argument('--output-dir', default='./dialogue_output', help='Output directory for dialogue versions')
    parser.add_argument('--api-key', help='Anthropic API key')

    args = parser.parse_args()

    blog_dir = Path(args.blog_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Initialize agent
    print("🚀 Initializing MIMO Podcast Agent...")
    agent = PodcastMIMOAgent(api_key=args.api_key)

    # Track results
    results = {
        "success": [],
        "failed": [],
        "not_found": []
    }

    print(f"\n📚 Regenerating {len(TARGET_POSTS)} posts as dialogue...\n")

    for i, slug in enumerate(TARGET_POSTS, 1):
        print(f"\n{'='*60}")
        print(f"Post {i}/{len(TARGET_POSTS)}: {slug}")
        print(f"{'='*60}")

        # Find blog post file
        blog_file = find_blog_post_file(blog_dir, slug)

        if not blog_file:
            print(f"❌ Blog post not found: {slug}")
            results["not_found"].append(slug)
            continue

        print(f"✅ Found: {blog_file.name}")

        # Generate output path
        output_file = output_dir / f"{slug}_dialogue.mp3"

        # Generate dialogue podcast
        try:
            result = agent.generate_podcast(str(blog_file), str(output_file))

            if result['success']:
                results["success"].append({
                    "slug": slug,
                    "audio": str(output_file),
                    "script": result['script_path'],
                    "certificate": result['certificate']
                })
                print(f"\n✅ SUCCESS: {slug}")
            else:
                results["failed"].append({
                    "slug": slug,
                    "reason": "Quality gates failed",
                    "certificate": result['certificate']
                })
                print(f"\n⚠️  FAILED: {slug} (quality gates)")

        except Exception as e:
            results["failed"].append({
                "slug": slug,
                "reason": str(e)
            })
            print(f"\n❌ ERROR: {slug}")
            print(f"   {str(e)}")

    # Save summary
    summary_file = output_dir / "regeneration_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(results, f, indent=2)

    # Print summary
    print(f"\n\n{'='*60}")
    print("📊 REGENERATION SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Success: {len(results['success'])}")
    print(f"❌ Failed: {len(results['failed'])}")
    print(f"🔍 Not Found: {len(results['not_found'])}")
    print(f"\nSummary saved to: {summary_file}")

    if results['success']:
        print(f"\n🎧 Dialogue versions saved to: {output_dir}/")
        print("\nNow you can compare:")
        for item in results['success']:
            print(f"  - {item['slug']}")
            print(f"    Narration: https://dsai-2025-asu.s3.amazonaws.com/audio/{item['slug']}.mp3")
            print(f"    Dialogue:  {item['audio']}")
            print(f"    Quality:   R={item['certificate']['R']:.2f} S={item['certificate']['S']:.2f} N={item['certificate']['N']:.2f} kappa={item['certificate']['kappa']:.2f}")
            print()


if __name__ == '__main__':
    main()
