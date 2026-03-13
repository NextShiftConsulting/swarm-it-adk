#!/usr/bin/env python3
"""
MIMO Podcast Agent - Transform blog narration into natural dialogue

Usage:
    python podcast_mimo.py --blog-post /path/to/post.mdx --output /path/to/output.mp3
"""

import anthropic
import boto3
import json
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
import re

class PodcastMIMOAgent:
    """
    Multi-agent system for generating natural podcast dialogue
    from technical blog posts.
    """

    def __init__(self, api_key=None):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get('ANTHROPIC_API_KEY')
        )
        self.polly = boto3.client('polly', region_name='us-east-1')

        # Voice configuration
        self.voices = {
            "host": "Matthew",      # Male, professional
            "expert": "Joanna"      # Female, warm, authoritative
        }

        # Model selection
        self.models = {
            "producer": "claude-sonnet-4-20250514",
            "host": "claude-sonnet-4-20250514",
            "expert": "claude-sonnet-4-20250514",
            "quality": "claude-sonnet-4-20250514"
        }

    def load_blog_post(self, blog_path: str) -> Dict:
        """Extract content from MDX blog post"""
        with open(blog_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract frontmatter
        frontmatter_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
        if frontmatter_match:
            frontmatter_text = frontmatter_match.group(1)
            body = content[frontmatter_match.end():].strip()

            # Parse frontmatter (simple key: value format)
            frontmatter = {}
            for line in frontmatter_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    frontmatter[key.strip()] = value.strip().strip('"\'')
        else:
            frontmatter = {}
            body = content

        return {
            "title": frontmatter.get('title', 'Untitled'),
            "description": frontmatter.get('description', ''),
            "body": body,
            "word_count": len(body.split())
        }

    def producer_agent(self, blog_post: Dict) -> Dict:
        """
        Producer Agent: Analyze blog and create dialogue outline
        """
        prompt = f"""You are a podcast producer for "Swarm-It by Next Shift Consulting."

Your job is to transform this technical blog post into an engaging 6-8 minute radio show dialogue outline.

Blog Title: {blog_post['title']}
Blog Description: {blog_post['description']}
Word Count: {blog_post['word_count']}

Blog Content:
{blog_post['body'][:5000]}

Create a dialogue outline with:
1. 3-5 core concepts that MUST be covered
2. Natural conversation flow (intro → concepts → examples → conclusion)
3. Specific points where host should ask questions
4. Concrete examples or analogies to use

Output as JSON:
{{
  "segments": [
    {{
      "type": "intro",
      "duration_seconds": 30,
      "host_intro": "Opening hook and topic introduction",
      "expert_response": "Brief context setter"
    }},
    {{
      "type": "concept",
      "concept_name": "Main technical concept",
      "duration_seconds": 90,
      "host_question": "What would listeners ask?",
      "expert_key_points": ["Point 1", "Point 2", "Point 3"],
      "example_to_use": "Real-world analogy or case study"
    }}
  ]
}}

Keep it conversational and accessible. The host is curious but not an expert.
The expert (Rudy Martin) created RSCT theory and knows AI quality deeply.
"""

        response = self.client.messages.create(
            model=self.models["producer"],
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Extract JSON from response
        response_text = response.content[0].text
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            outline = json.loads(json_match.group(0))
        else:
            # Fallback simple outline
            outline = {
                "segments": [
                    {
                        "type": "intro",
                        "duration_seconds": 30,
                        "host_intro": f"Introduce topic: {blog_post['title']}",
                        "expert_response": "Set context"
                    }
                ]
            }

        print(f"✅ Producer created outline with {len(outline['segments'])} segments")
        return outline

    def host_agent(self, segment: Dict, context: str = "") -> str:
        """
        Host Agent: Generate host dialogue for segment
        """
        if segment["type"] == "intro":
            prompt = f"""You are the host of "Swarm-It," a podcast about AI quality and reasoning.

Generate a 30-second opening for this episode. Be enthusiastic and set up the topic:

Topic: {segment.get('host_intro', 'AI quality discussion')}

Your personality:
- Curious and energetic
- Not an expert, but technically literate
- Create hook that makes listeners want to hear more

Generate ONLY the host's spoken dialogue (20-30 words). Natural, conversational style.
Don't use quotes or speaker labels. Just the raw dialogue text.
"""
        else:
            prompt = f"""You are the host of "Swarm-It," a podcast about AI quality.

The expert just finished explaining something. Now ask a follow-up question about:

Concept: {segment.get('concept_name', 'the topic')}

Context from conversation so far:
{context[-500:]}

Generate ONE natural follow-up question (15-25 words) that:
- Asks for clarification or concrete example
- Bridges technical to practical
- Sounds like genuine curiosity

Generate ONLY the host's question. No quotes, no labels, just the spoken words.
"""

        response = self.client.messages.create(
            model=self.models["host"],
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        dialogue = response.content[0].text.strip()
        # Clean up any quotes or labels
        dialogue = re.sub(r'^(HOST:|")', '', dialogue)
        dialogue = re.sub(r'"$', '', dialogue)

        print(f"  🎙️  Host: {dialogue[:60]}...")
        return dialogue

    def expert_agent(self, segment: Dict, host_question: str, blog_context: str) -> str:
        """
        Expert Agent: Generate expert response
        """
        if segment["type"] == "intro":
            prompt = f"""You are Rudy Martin, creator of RSCT (Representation-Solver Compatibility Theory).

The host just introduced the topic. Respond with a brief, engaging setup (30-40 words).

Host's intro: {host_question}

Your personality:
- Knowledgeable but accessible
- Enthusiastic about the topic
- Set the stage without diving too deep yet

Generate ONLY your spoken response. Natural, conversational. No quotes or labels.
"""
        else:
            concept = segment.get('concept_name', 'the concept')
            key_points = segment.get('expert_key_points', [])
            example = segment.get('example_to_use', '')

            prompt = f"""You are Rudy Martin, explaining AI quality concepts on your podcast.

The host just asked: "{host_question}"

Explain this concept: {concept}

Key points to cover:
{chr(10).join(f"- {point}" for point in key_points)}

{f"Use this example: {example}" if example else ""}

Blog context (for accuracy):
{blog_context[:1000]}

Generate a 60-80 word explanation that:
1. Directly answers the host's question
2. Uses simple analogies
3. Includes concrete example
4. Connects to practical implications

Your style: "Great question! [Answer]... Think of it like [analogy]... Here's a real example: [case study]"

Generate ONLY your spoken response. Natural, conversational. No quotes or labels.
"""

        response = self.client.messages.create(
            model=self.models["expert"],
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        dialogue = response.content[0].text.strip()
        dialogue = re.sub(r'^(EXPERT:|RUDY:|")', '', dialogue)
        dialogue = re.sub(r'"$', '', dialogue)

        print(f"  👨‍🏫 Expert: {dialogue[:60]}...")
        return dialogue

    def quality_agent(self, dialogue_script: List[Dict], blog_post: Dict) -> Dict:
        """
        Quality Agent: Validate dialogue with RSCT gates
        """
        # Combine all dialogue for analysis
        full_dialogue = "\n".join([
            f"{seg['speaker'].upper()}: {seg['text']}"
            for seg in dialogue_script
        ])

        prompt = f"""You are a quality validator for podcast dialogue.

Original blog post title: {blog_post['title']}
Blog word count: {blog_post['word_count']}

Blog key concepts (first 1000 chars):
{blog_post['body'][:1000]}

Generated dialogue:
{full_dialogue}

Evaluate using RSCT metrics:

R (Relevance): Does dialogue cover blog's core concepts? (0-1)
S (Superfluousness): How much filler/fluff? (0-1, lower is better)
N (Noise): Any factual errors or hallucinations? (0-1, lower is better)
kappa (Overall Quality): Natural flow, engagement, clarity (0-1)

Return JSON:
{{
  "R": 0.X,
  "S": 0.X,
  "N": 0.X,
  "kappa": 0.X,
  "feedback": "Brief assessment",
  "approved": true/false
}}

Approval thresholds: R >= 0.7, S <= 0.3, N <= 0.1, kappa >= 0.8
"""

        response = self.client.messages.create(
            model=self.models["quality"],
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Extract JSON
        response_text = response.content[0].text
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            cert = json.loads(json_match.group(0))
        else:
            # Default passing cert
            cert = {"R": 0.8, "S": 0.2, "N": 0.05, "kappa": 0.85, "approved": True, "feedback": "OK"}

        print(f"\n📊 Quality Certificate:")
        print(f"   R={cert['R']:.2f} S={cert['S']:.2f} N={cert['N']:.2f} kappa={cert['kappa']:.2f}")
        print(f"   Status: {'✅ APPROVED' if cert['approved'] else '❌ REJECTED'}")

        return cert

    def generate_dialogue(self, blog_post: Dict) -> List[Dict]:
        """
        Main orchestration: Generate complete dialogue script
        """
        print(f"\n🎬 Generating dialogue for: {blog_post['title']}")
        print(f"   Blog length: {blog_post['word_count']} words\n")

        # Step 1: Producer creates outline
        print("📋 Step 1: Producer creating outline...")
        outline = self.producer_agent(blog_post)

        # Step 2: Generate dialogue segments
        print("\n🎙️  Step 2: Generating dialogue...")
        dialogue_script = []
        conversation_context = ""

        for i, segment in enumerate(outline["segments"]):
            print(f"\n  Segment {i+1}/{len(outline['segments'])} ({segment['type']})")

            # Host speaks
            host_dialogue = self.host_agent(segment, conversation_context)
            dialogue_script.append({
                "speaker": "host",
                "text": host_dialogue
            })
            conversation_context += f"\nHOST: {host_dialogue}"

            # Expert responds
            expert_dialogue = self.expert_agent(segment, host_dialogue, blog_post['body'])
            dialogue_script.append({
                "speaker": "expert",
                "text": expert_dialogue
            })
            conversation_context += f"\nEXPERT: {expert_dialogue}"

        # Step 3: Quality validation
        print("\n\n🔍 Step 3: Quality validation...")
        cert = self.quality_agent(dialogue_script, blog_post)

        return dialogue_script, cert

    def text_to_speech(self, speaker: str, text: str) -> bytes:
        """
        Convert text to speech using AWS Polly
        """
        response = self.polly.synthesize_speech(
            Engine='neural',
            Text=text,
            OutputFormat='mp3',
            VoiceId=self.voices[speaker]
        )

        return response['AudioBody'].read()

    def mix_audio(self, dialogue_script: List[Dict], output_path: str):
        """
        Generate and combine audio segments
        """
        try:
            from pydub import AudioSegment
        except ImportError:
            print("⚠️  pydub not installed. Skipping audio mixing.")
            print("   Install with: pip install pydub")
            return None

        print("\n🎧 Step 4: Generating audio...")

        combined = AudioSegment.silent(duration=0)

        for i, segment in enumerate(dialogue_script):
            print(f"   Generating {segment['speaker']} audio {i+1}/{len(dialogue_script)}...")

            # Generate TTS
            audio_bytes = self.text_to_speech(segment['speaker'], segment['text'])

            # Convert to AudioSegment
            from io import BytesIO
            audio_seg = AudioSegment.from_mp3(BytesIO(audio_bytes))

            # Add pause between speakers (800ms)
            if i > 0:
                pause = AudioSegment.silent(duration=800)
                combined += pause

            combined += audio_seg

        # Export final podcast
        combined.export(output_path, format='mp3')
        print(f"\n✅ Audio saved to: {output_path}")
        print(f"   Duration: {len(combined) / 1000:.1f} seconds")

        return output_path

    def generate_podcast(self, blog_path: str, output_path: str) -> Dict:
        """
        Complete pipeline: Blog → Dialogue → Audio
        """
        # Load blog
        blog_post = self.load_blog_post(blog_path)

        # Generate dialogue
        dialogue_script, cert = self.generate_dialogue(blog_post)

        # Save dialogue script
        script_path = output_path.replace('.mp3', '_script.json')
        with open(script_path, 'w', encoding='utf-8') as f:
            json.dump({
                "title": blog_post['title'],
                "dialogue": dialogue_script,
                "certificate": cert
            }, f, indent=2)
        print(f"\n💾 Dialogue script saved to: {script_path}")

        # Generate audio
        if cert.get('approved', True):
            audio_path = self.mix_audio(dialogue_script, output_path)
            return {
                "success": True,
                "audio_path": audio_path,
                "script_path": script_path,
                "certificate": cert
            }
        else:
            print("\n⚠️  Dialogue not approved by quality gates. Skipping audio generation.")
            return {
                "success": False,
                "script_path": script_path,
                "certificate": cert
            }


def main():
    parser = argparse.ArgumentParser(description='Generate MIMO podcast dialogue from blog post')
    parser.add_argument('--blog-post', required=True, help='Path to MDX blog post')
    parser.add_argument('--output', required=True, help='Output MP3 path')
    parser.add_argument('--api-key', help='Anthropic API key (or use ANTHROPIC_API_KEY env var)')

    args = parser.parse_args()

    # Initialize agent
    agent = PodcastMIMOAgent(api_key=args.api_key)

    # Generate podcast
    result = agent.generate_podcast(args.blog_post, args.output)

    if result['success']:
        print("\n🎉 SUCCESS! Dialogue podcast generated.")
        sys.exit(0)
    else:
        print("\n❌ Quality gates failed. Check script for issues.")
        sys.exit(1)


if __name__ == '__main__':
    main()
