#!/usr/bin/env python3
"""
MIMO Podcast Agent - Transform blog narration into natural dialogue

Usage:
    python podcast_mimo.py --blog-post /path/to/post.mdx --output /path/to/output.mp3

Options:
    --provider       LLM provider: mimo or xiami (default: xiami)
    --tts-provider   TTS provider: elevenlabs or polly (default: elevenlabs)

TTS Voices:
    ElevenLabs: Maya (host), Rudy (expert) - higher quality, requires ELEVENLABS_API_KEY
    AWS Polly:  Matthew (host), Joanna (expert) - lower cost, requires AWS credentials
"""

import boto3
import json
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List
import re
import requests

# P18 v3.0 - Unified credential access
try:
    from swarm_auth import get_credential, has_credential
    HAS_SWARM_AUTH = True
except ImportError:
    HAS_SWARM_AUTH = False
    print("[!] swarm-auth not found. Using basic environment variable fallback.")
    # Fallback implementations
    def get_credential(key, default=None):
        return os.environ.get(key, default)
    def has_credential(key):
        return os.environ.get(key) is not None

class PodcastMIMOAgent:
    """
    Multi-agent system for generating natural podcast dialogue
    from technical blog posts.
    """

    def __init__(self, provider="mimo", tts_provider="elevenlabs"):
        self.provider = provider
        self.tts_provider = tts_provider

        # P18 v3.0 - Unified credential access (no prefix needed)
        if provider == "mimo":
            # Xiaomi MiMo cloud API (cost-effective alternative to US providers)
            # Try both standard and SWARM_ prefixed names for backwards compatibility
            self.api_key = get_credential('MIMO_API_KEY') or get_credential('SWARM_MIMO_API_KEY')
            self.endpoint = get_credential('MIMO_ENDPOINT') or get_credential('SWARM_MIMO_ENDPOINT', 'https://api.xiaomimimo.com/v1')
            self.model = get_credential('MIMO_MODEL') or get_credential('SWARM_MIMO_MODEL', 'mimo-v2-flash')
            if not self.api_key:
                raise ValueError("MIMO_API_KEY not found. Set environment variable or use --provider xiami for local Ollama.")
        elif provider == "xiami":
            # Local Ollama endpoint (free but requires local setup)
            self.endpoint = get_credential('XIAMI_ENDPOINT') or get_credential('SWARM_XIAMI_ENDPOINT', 'http://localhost:11434/api/generate')
            self.model = get_credential('XIAMI_MODEL') or get_credential('SWARM_XIAMI_MODEL', 'llama2')
            self.api_key = get_credential('XIAMI_API_KEY') or get_credential('SWARM_XIAMI_API_KEY')  # Optional
        else:
            raise ValueError(f"Unsupported provider: {provider}. Use 'mimo' or 'xiami'.")

        # P18 v3.0 - AWS credentials for Polly
        try:
            from swarm_auth import get_aws_credentials
            aws_creds = get_aws_credentials()
            if aws_creds.get('aws_access_key_id') and aws_creds.get('aws_secret_access_key'):
                self.polly = boto3.client(
                    'polly',
                    aws_access_key_id=aws_creds['aws_access_key_id'],
                    aws_secret_access_key=aws_creds['aws_secret_access_key'],
                    region_name=aws_creds.get('region_name', 'us-east-1')
                )
            else:
                # Fall back to default boto3 credential chain
                self.polly = boto3.client('polly', region_name='us-east-1')
        except ImportError:
            # swarm_auth not available, use default chain
            self.polly = boto3.client('polly', region_name='us-east-1')

        # P18 v3.0 - ElevenLabs credentials
        self.elevenlabs_api_key = get_credential('ELEVENLABS_API_KEY')

        # Voice configuration - AWS Polly
        self.polly_voices = {
            "host": "Matthew",      # Male, professional
            "expert": "Joanna"      # Female, warm, authoritative
        }

        # Voice configuration - ElevenLabs (higher quality)
        self.elevenlabs_voices = {
            "host": {
                "id": get_credential('ELEVENLABS_HOST_VOICE_ID') or 'XB0fDUnXU5powFXDhCwa',  # Charlotte
                "name": "Maya",
                "settings": {
                    "stability": 0.75,
                    "similarity_boost": 0.6,
                    "style": 0.1,
                    "use_speaker_boost": False,
                }
            },
            "expert": {
                "id": get_credential('ELEVENLABS_RUDY_VOICE_ID') or get_credential('ELEVENLABS_EXPERT_VOICE_ID') or 'P39vtd0NQF1OwoxKSFaF',  # Rudy
                "name": "Rudy",
                "settings": {
                    "stability": 0.4,
                    "similarity_boost": 0.75,
                    "style": 0.3,
                    "use_speaker_boost": True,
                }
            }
        }

        # Legacy alias for backwards compatibility
        self.voices = self.polly_voices

        # Model selection for all agents
        self.models = {
            "producer": self.model,
            "host": self.model,
            "expert": self.model,
            "quality": self.model
        }

        print("[*] Initialized MIMO Agent")
        print(f"    LLM Provider: {self.provider}")
        print(f"    LLM Endpoint: {self.endpoint}")
        print(f"    LLM Model: {self.model}")
        print(f"    TTS Provider: {self.tts_provider}")
        if self.tts_provider == "elevenlabs":
            print(f"    TTS Voices: {self.elevenlabs_voices['host']['name']} (host), {self.elevenlabs_voices['expert']['name']} (expert)")

    def call_llm(self, prompt: str, max_tokens: int = 2000) -> str:
        """
        Generic LLM call supporting multiple providers
        """
        if self.provider == "mimo":
            return self._call_mimo(prompt, max_tokens)
        elif self.provider == "xiami":
            return self._call_xiami(prompt, max_tokens)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _call_mimo(self, prompt: str, max_tokens: int) -> str:
        """
        Call Xiaomi MiMo cloud API (OpenAI-compatible endpoint)
        """
        try:
            response = requests.post(
                f"{self.endpoint}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.7
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[!] MiMo API call failed: {e}")
            return ""

    def _call_xiami(self, prompt: str, max_tokens: int) -> str:
        """
        Call XIAMI/Ollama local endpoint
        """
        try:
            response = requests.post(
                self.endpoint,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.7
                    }
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            return result.get('response', '')
        except Exception as e:
            print(f"[!] XIAMI call failed: {e}")
            return ""

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
The expert (Rudy Martin) explains concepts from the blog post using clear analogies and examples.

CRITICAL GROUNDING RULES:
1. Stay faithful to the blog content. Do NOT introduce external frameworks, theories,
   or concepts unless they are explicitly discussed in the blog text above.
2. FORBIDDEN unless explicitly in blog: "RSCT", "Representation-Solver Compatibility Theory",
   "alpha-omega", "compatibility certificate", "context quality certificate", "kappa score".
3. ONLY use terminology that appears verbatim in the blog text.
4. The expert should explain what's IN THE BLOG, not inject proprietary theories.
"""

        response_text = self.call_llm(prompt, max_tokens=4000)

        # Extract JSON from response
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

        print(f"[+] Producer created outline with {len(outline['segments'])} segments")
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

        dialogue = self.call_llm(prompt, max_tokens=200).strip()
        # Clean up any quotes or labels
        dialogue = re.sub(r'^(HOST:|")', '', dialogue)
        dialogue = re.sub(r'"$', '', dialogue)

        print(f"  [2]  Host: {dialogue[:60]}...")
        return dialogue

    def expert_agent(self, segment: Dict, host_question: str, blog_context: str) -> str:
        """
        Expert Agent: Generate expert response
        """
        if segment["type"] == "intro":
            prompt = f"""You are Rudy Martin, a technical expert explaining AI concepts on the "Swarm-It" podcast.

The host just introduced the topic. Respond with a brief, engaging setup (30-40 words).

Host's intro: {host_question}

Your personality:
- Knowledgeable but accessible
- Enthusiastic about the topic
- Set the stage without diving too deep yet

CRITICAL: Explain only what's in the blog post. Do NOT introduce external theories or frameworks
unless they are explicitly mentioned in the blog content. FORBIDDEN terms (unless in blog):
"RSCT", "Representation-Solver Compatibility Theory", "compatibility certificate".

Generate ONLY your spoken response. Natural, conversational. No quotes or labels.
"""
        else:
            concept = segment.get('concept_name', 'the concept')
            key_points = segment.get('expert_key_points', [])
            example = segment.get('example_to_use', '')

            prompt = f"""You are Rudy Martin, a technical expert explaining concepts from a blog post on the "Swarm-It" podcast.

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

CRITICAL GROUNDING RULES:
1. Stay faithful to the blog content. Explain ONLY what's IN THE BLOG.
2. FORBIDDEN unless blog mentions them: "RSCT", "Representation-Solver Compatibility Theory",
   "alpha-omega", "compatibility certificate", "context quality certificate", "kappa score".
3. Do NOT introduce external frameworks, theories, or concepts not explicitly in the blog.
4. If the blog doesn't mention a solution, don't invent one.
5. Use the blog's OWN terminology, not proprietary terms from other sources.

Your style: Vary your openings (don't always say "Great question!"). Use analogies from the blog context.

Generate ONLY your spoken response. Natural, conversational. No quotes or labels.
"""

        dialogue = self.call_llm(prompt, max_tokens=400).strip()
        dialogue = re.sub(r'^(EXPERT:|RUDY:|")', '', dialogue)
        dialogue = re.sub(r'"$', '', dialogue)

        print(f"  [E] Expert: {dialogue[:60]}...")
        return dialogue

    def podcast_peer_agent(self, dialogue_script: List[Dict], blog_post: Dict) -> Dict:
        """
        Podcast Peer Agent: Editorial quality review (Stage 1 of 2)

        Evaluates dialogue from a peer reviewer perspective:
        - Dialogue flow and naturalness
        - Accuracy to source material
        - Engagement and clarity
        - Host-expert dynamics
        - Forbidden terminology detection
        """
        full_dialogue = "\n".join([
            f"{seg['speaker'].upper()}: {seg['text']}"
            for seg in dialogue_script
        ])

        prompt = f"""You are a podcast editor reviewing dialogue quality for "Swarm-It" podcast.

**Source Blog:**
Title: {blog_post['title']}
Word Count: {blog_post['word_count']}
Content (first 2000 chars):
{blog_post['body'][:2000]}

**Generated Dialogue:**
{full_dialogue}

**Review Criteria:**

1. **Source Fidelity** (0-10): Does dialogue accurately represent the blog's content?
   - Are key concepts from the blog covered?
   - Any misrepresentations or distortions?

2. **Hallucination Check** (0-10, higher = cleaner): Does dialogue introduce content NOT in the blog?
   - FORBIDDEN terms (unless in blog): "RSCT", "Representation-Solver Compatibility Theory",
     "alpha-omega", "compatibility certificate", "context quality certificate", "kappa score"
   - Any invented facts, statistics, or claims?

3. **Dialogue Flow** (0-10): Is the conversation natural and engaging?
   - Does host ask genuine questions?
   - Does expert explain clearly without lecturing?
   - Natural turn-taking?

4. **Filler Detection** (0-10, higher = less filler): How much unnecessary padding?
   - Repetitive phrases ("Great question!")
   - Redundant explanations
   - Conversational fluff that doesn't add value

5. **Engagement** (0-10): Would listeners stay tuned?
   - Hook in the opening?
   - Clear examples and analogies?
   - Satisfying conclusion?

**Return JSON:**
{{
  "source_fidelity": X,
  "hallucination_check": X,
  "dialogue_flow": X,
  "filler_detection": X,
  "engagement": X,
  "overall_score": X.X,
  "issues": ["list of specific issues found"],
  "forbidden_terms_found": ["list any forbidden terms used"],
  "recommendation": "PASS | REVISE | REJECT"
}}
"""
        response_text = self.call_llm(prompt, max_tokens=800)

        # Extract JSON
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                peer_review = json.loads(json_match.group(0))
            except json.JSONDecodeError:
                peer_review = self._default_peer_review()
        else:
            peer_review = self._default_peer_review()

        # Ensure all fields exist
        peer_review.setdefault('source_fidelity', 7)
        peer_review.setdefault('hallucination_check', 7)
        peer_review.setdefault('dialogue_flow', 7)
        peer_review.setdefault('filler_detection', 7)
        peer_review.setdefault('engagement', 7)
        peer_review.setdefault('issues', [])
        peer_review.setdefault('forbidden_terms_found', [])
        peer_review.setdefault('recommendation', 'PASS')

        # Calculate overall if not provided
        if 'overall_score' not in peer_review:
            scores = [peer_review['source_fidelity'], peer_review['hallucination_check'],
                      peer_review['dialogue_flow'], peer_review['filler_detection'],
                      peer_review['engagement']]
            peer_review['overall_score'] = sum(scores) / len(scores)

        print("\n[*] Podcast Peer Review (Stage 1/2):")
        print(f"    Source Fidelity: {peer_review['source_fidelity']}/10")
        print(f"    Hallucination Check: {peer_review['hallucination_check']}/10")
        print(f"    Dialogue Flow: {peer_review['dialogue_flow']}/10")
        print(f"    Filler Detection: {peer_review['filler_detection']}/10")
        print(f"    Engagement: {peer_review['engagement']}/10")
        print(f"    Overall: {peer_review['overall_score']:.1f}/10")
        print(f"    Recommendation: {peer_review['recommendation']}")
        if peer_review['forbidden_terms_found']:
            print(f"    [!] Forbidden terms: {peer_review['forbidden_terms_found']}")

        return peer_review

    def _default_peer_review(self) -> Dict:
        """Default peer review for fallback"""
        return {
            "source_fidelity": 7,
            "hallucination_check": 7,
            "dialogue_flow": 7,
            "filler_detection": 7,
            "engagement": 7,
            "overall_score": 7.0,
            "issues": [],
            "forbidden_terms_found": [],
            "recommendation": "PASS"
        }

    def podcast_rsct_agent(self, dialogue_script: List[Dict], blog_post: Dict, peer_review: Dict) -> Dict:
        """
        Podcast RSCT Agent: Quality certification (Stage 2 of 2)

        Applies RSCT framework:
        - R/S/N semantic decomposition
        - 4-gate sequential validation
        - Certificate generation
        - Typed decision: EXECUTE, RE_ENCODE, REJECT, REPAIR, BLOCK
        """
        full_dialogue = "\n".join([
            f"{seg['speaker'].upper()}: {seg['text']}"
            for seg in dialogue_script
        ])

        # Incorporate peer review findings into RSCT prompt
        peer_context = ""
        if peer_review.get('forbidden_terms_found'):
            peer_context += f"\nPeer Review WARNING: Forbidden terms detected: {peer_review['forbidden_terms_found']}"
        if peer_review.get('issues'):
            peer_context += f"\nPeer Review Issues: {peer_review['issues'][:3]}"  # Top 3 issues

        prompt = f"""You are an RSCT certification specialist applying quality gates to podcast dialogue.

**Source Blog:**
Title: {blog_post['title']}
Word Count: {blog_post['word_count']}
Content (first 2000 chars):
{blog_post['body'][:2000]}

**Generated Dialogue:**
{full_dialogue}
{peer_context}

**RSCT Semantic Decomposition:**

Score each dimension 0.0-1.0, ensuring R + S + N = 1.0:

R (Relevance): Fraction covering blog's core concepts accurately
S (Superfluous): Fraction that is filler, repetition, or off-topic padding
N (Noise): Fraction that is hallucinated or factually incorrect
  - Any forbidden terms not in blog = high N
  - Invented facts/statistics = high N

**Return JSON:**
{{
  "R": 0.X,
  "S": 0.X,
  "N": 0.X,
  "feedback": "Brief R/S/N breakdown explanation",
  "hallucination_details": "Specific hallucinations found, if any"
}}
"""
        response_text = self.call_llm(prompt, max_tokens=500)

        # Extract JSON
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            decomp = json.loads(json_match.group(0))
        else:
            # Default decomposition
            decomp = {"R": 0.7, "S": 0.2, "N": 0.1, "feedback": "Default decomposition"}

        # Normalize to ensure R + S + N = 1.0
        total = decomp['R'] + decomp['S'] + decomp['N']
        if total > 0:
            decomp['R'] /= total
            decomp['S'] /= total
            decomp['N'] /= total

        # Derive quality metric α = R / (R + N)
        alpha = decomp['R'] / (decomp['R'] + decomp['N']) if (decomp['R'] + decomp['N']) > 0 else 0.5

        # Path 2: Compatibility Assessment (κ_gate, σ, c)
        # For podcast dialogue, κ_gate = "dialogue-blog alignment"
        # σ = "conversational turbulence" (repetition, contradiction)
        # c = "host-expert consensus" (coherence)

        # Simple proxy: κ_compat ≈ R (content alignment) — R*(1-N) proxy
        # σ ≈ S (more filler → more turbulence)
        # c ≈ 1 - N (fewer errors → better consensus)
        kappa_compat = decomp['R']  # Blog-dialogue alignment (R*(1-N) proxy)
        sigma = decomp['S']  # Conversational turbulence (filler)
        coherence = 1.0 - decomp['N']  # Inverse of noise

        # === CONTROL LAYER: Sequential 4-Gate Validation ===

        # Thresholds (from FIG. 24)
        N_thr = 0.5      # Gate 1: Noise floor (Fano's inequality)
        c_min = 0.4      # Gate 2: Coherence minimum
        sigma_thr = 0.5  # Gate 3: Hard turbulence barrier
        kappa_base = 0.5 # Gate 3: Compatibility base
        lambda_t = 0.4   # Gate 3: Turbulence sensitivity
        kappa_L_min = 0.3  # Gate 4: Modal compatibility minimum

        decision = "EXECUTE"
        gate_failed = None
        gate_feedback = ""

        # Gate 1: Integrity Guard (Noise Floor)
        if decomp['N'] >= N_thr:
            decision = "REJECT"
            gate_failed = 1
            gate_feedback = f"Gate 1 (Integrity): N={decomp['N']:.2f} >= {N_thr} (noise saturation). Fano's inequality: no solver can recover correct inference."

        # Gate 2: Consensus Gate (Coherence)
        elif coherence < c_min:
            decision = "BLOCK"
            gate_failed = 2
            gate_feedback = f"Gate 2 (Consensus): c={coherence:.2f} < {c_min} (structural incoherence). Host-expert dialogue lacks consistency."

        # Gate 3: Admissibility Gate (Dynamic Compatibility)
        elif sigma > sigma_thr:
            decision = "RE_ENCODE"
            gate_failed = 3
            gate_feedback = f"Gate 3 (Admissibility): σ={sigma:.2f} > {sigma_thr} (hard turbulence barrier). Too much filler/repetition."
        elif kappa_compat < (kappa_base + lambda_t * sigma):
            decision = "RE_ENCODE"
            gate_failed = 3
            kappa_req = kappa_base + lambda_t * sigma
            gate_feedback = f"Gate 3 (Admissibility): κ={kappa_compat:.2f} < κ_req={kappa_req:.2f} (dynamic threshold). Blog-dialogue alignment insufficient."

        # Gate 4: Grounding Gate (Modal Compatibility)
        # For podcast: κ_L = "low-level quality" (pacing, natural flow)
        # Proxy: κ_L ≈ overall engagement quality (kappa)
        kappa_L = alpha * kappa_compat  # Combined quality * alignment
        if kappa_L < kappa_L_min:
            decision = "REPAIR"
            gate_failed = 4
            gate_feedback = f"Gate 4 (Grounding): κ_L={kappa_L:.2f} < {kappa_L_min} (physically ungrounded quality). Dialogue lacks natural flow."

        # === Map to Execution States (FIG. 19) ===

        # State classification based on (α, κ_gate) conjunction
        if alpha >= 0.7 and kappa_compat >= 0.7:
            execution_state = "HEALTHY"  # High quality, high alignment
        elif alpha >= 0.7 and kappa_compat < 0.7:
            execution_state = "HALLUCINATION-RISK"  # High quality but misaligned
        elif alpha < 0.7 and kappa_compat >= 0.7:
            execution_state = "TARGETED-POISONING"  # Low quality despite alignment (adversarial)
        else:
            execution_state = "SYSTEMIC-DEGRADATION"  # Both low

        # === STRUCTURED COMPATIBILITY CERTIFICATE ===

        certificate = {
            # DECOMPOSITION section (1402)
            "R": decomp['R'],
            "S": decomp['S'],
            "N": decomp['N'],

            # QUALITY section (1404)
            "alpha": alpha,  # Quality metric from semantic decomposition
            "omega": 1.0,    # Reliability coefficient (not computed for simple case)
            "alpha_omega": alpha,  # Reliability-adjusted quality
            "tau": 1.0 / alpha if alpha > 0 else 2.0,  # Temperature (not a gate operand)

            # DERIVED section (1406)
            "kappa_compat": kappa_compat,  # Execution compatibility score
            "sigma": sigma,  # Turbulence metric
            "coherence": coherence,  # Consensus coherence

            # DIAGNOSTIC section (1407) - simplified
            "kappa_L": kappa_L,  # Low-level modal health

            # COLLAPSE_TYPE section (1408)
            "execution_state": execution_state,
            "decision": decision,
            "gate_failed": gate_failed,
            "gate_feedback": gate_feedback if gate_failed else "All gates passed",

            # Legacy fields for compatibility
            "kappa": alpha * kappa_compat,  # Overall quality score
            "approved": (decision == "EXECUTE"),
            "feedback": decomp.get('feedback', '') + ("\n" + gate_feedback if gate_feedback else "")
        }

        # Include peer review in certificate
        certificate['peer_review'] = {
            'overall_score': peer_review.get('overall_score', 0),
            'recommendation': peer_review.get('recommendation', 'UNKNOWN'),
            'forbidden_terms': peer_review.get('forbidden_terms_found', []),
            'issues': peer_review.get('issues', [])
        }

        print("\n[*] RSCT Quality Certificate (Stage 2/2):")
        print(f"    DECOMPOSITION: R={certificate['R']:.2f} S={certificate['S']:.2f} N={certificate['N']:.2f}")
        print(f"    QUALITY: alpha={certificate['alpha']:.2f}")
        print(f"    DERIVED: kappa={certificate['kappa_compat']:.2f} sigma={certificate['sigma']:.2f} c={certificate['coherence']:.2f}")
        print(f"    EXECUTION STATE: {certificate['execution_state']}")
        print(f"    DECISION: {certificate['decision']} (Gate {certificate['gate_failed'] or 'ALL PASSED'})")
        print(f"    Status: {'[+] EXECUTE' if certificate['approved'] else '[-] ' + certificate['decision']}")

        return certificate

    def quality_agent(self, dialogue_script: List[Dict], blog_post: Dict) -> Dict:
        """
        Two-Stage Quality Review: Peer + RSCT

        Stage 1: podcast_peer_agent - Editorial quality review
        Stage 2: podcast_rsct_agent - RSCT certification with 4-gate validation

        Returns combined certificate with both reviews.
        """
        print(f"\n{'='*60}")
        print("[*] TWO-STAGE QUALITY REVIEW")
        print(f"{'='*60}")

        # Stage 1: Peer Review
        peer_review = self.podcast_peer_agent(dialogue_script, blog_post)

        # Stage 2: RSCT Certification (informed by peer review)
        certificate = self.podcast_rsct_agent(dialogue_script, blog_post, peer_review)

        # Combined summary
        print(f"\n{'='*60}")
        print("[*] COMBINED REVIEW SUMMARY")
        print(f"{'='*60}")
        print(f"    Peer Review: {peer_review['overall_score']:.1f}/10 ({peer_review['recommendation']})")
        print(f"    RSCT: R={certificate['R']:.2f} S={certificate['S']:.2f} N={certificate['N']:.2f}")
        print(f"    Final Decision: {certificate['decision']}")
        print(f"{'='*60}")

        return certificate

    def generate_dialogue(self, blog_post: Dict) -> List[Dict]:
        """
        Main orchestration: Generate complete dialogue script with feedback loops

        Implements Loop 1 (Morph Repair) from patent architecture:
        - Non-EXECUTE decision → apply graph transformation operator
        - Re-derive certificate
        - Re-evaluate gates
        - Continue until EXECUTE or max attempts reached
        """
        print(f"\n[*] Generating dialogue for: {blog_post['title']}")
        print(f"    Blog length: {blog_post['word_count']} words\n")

        max_attempts = 2  # Prevent infinite loops
        attempt = 1

        while attempt <= max_attempts:
            if attempt > 1:
                print(f"\n[*] RETRY ATTEMPT {attempt}/{max_attempts} (Morph Repair Cycle)")

            # Step 1: Producer creates outline
            print("[1] Step 1: Producer creating outline...")
            outline = self.producer_agent(blog_post)

            # Step 2: Generate dialogue segments
            print("\n[2] Step 2: Generating dialogue...")
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

            # Step 3: Quality validation with state-based decision
            print("\n\n[3] Step 3: Quality validation...")
            cert = self.quality_agent(dialogue_script, blog_post)

            # === CONTROL LAYER: Act on typed decision ===

            if cert['decision'] == 'EXECUTE':
                # Gate passed - accept dialogue
                print("\n[+] Gate evaluation: EXECUTE (All gates passed)")
                return dialogue_script, cert

            elif cert['decision'] == 'RE_ENCODE':
                # Morph Repair: Regenerate dialogue
                print("\n[!] Gate evaluation: RE_ENCODE")
                print(f"    Reason: {cert['gate_feedback']}")
                if attempt < max_attempts:
                    print("    Applying graph transformation: regenerate dialogue")
                    attempt += 1
                    continue  # Retry loop
                else:
                    print("    Max attempts reached - returning failed dialogue")
                    return dialogue_script, cert

            elif cert['decision'] == 'REPAIR':
                # Morph Repair: Attempt targeted fix
                print("\n[!] Gate evaluation: REPAIR")
                print(f"    Reason: {cert['gate_feedback']}")
                if attempt < max_attempts:
                    print("    Applying graph transformation: regenerate dialogue")
                    attempt += 1
                    continue  # Retry loop
                else:
                    print("    Max attempts reached - returning failed dialogue")
                    return dialogue_script, cert

            elif cert['decision'] in ['REJECT', 'BLOCK']:
                # Terminal failure - no retry
                print(f"\n[-] Gate evaluation: {cert['decision']}")
                print(f"    Reason: {cert['gate_feedback']}")
                print("    Terminal failure - no retry")
                return dialogue_script, cert

            else:
                # Unknown decision - default to execute
                print(f"\n[?] Unknown decision: {cert['decision']} - defaulting to EXECUTE")
                return dialogue_script, cert

        # Should never reach here, but return if loop exits
        return dialogue_script, cert

    def _save_individual_audio_files(self, dialogue_script: List[Dict], output_path: str):
        """
        Fallback: Save individual MP3 files when pydub/ffmpeg not available
        """
        output_dir = Path(output_path).parent / f"{Path(output_path).stem}_segments"
        output_dir.mkdir(exist_ok=True)

        print(f"   [!] Saving individual MP3 segments to: {output_dir}/")

        for i, segment in enumerate(dialogue_script):
            speaker = segment['speaker']
            text = segment['text']

            # Generate filename
            filename = f"{i+1:02d}_{speaker}_{text[:30].replace(' ', '_')}.mp3"
            filepath = output_dir / filename

            print(f"   Generating {speaker} audio {i+1}/{len(dialogue_script)}...")

            # Generate TTS
            audio_bytes = self.text_to_speech(speaker, text)

            # Save to file
            with open(filepath, 'wb') as f:
                f.write(audio_bytes)

        print(f"\n[+] Individual MP3 segments saved to: {output_dir}/")
        print(f"   Total segments: {len(dialogue_script)}")
        print("\n[!] To combine segments, install ffmpeg:")
        print("   Windows: choco install ffmpeg")
        print("   Then re-run the script to generate combined MP3")

        return str(output_dir)

    def text_to_speech(self, speaker: str, text: str) -> bytes:
        """
        Convert text to speech using configured TTS provider
        """
        if self.tts_provider == "elevenlabs":
            return self._tts_elevenlabs(speaker, text)
        else:
            return self._tts_polly(speaker, text)

    def _tts_elevenlabs(self, speaker: str, text: str) -> bytes:
        """
        Convert text to speech using ElevenLabs API
        """
        if not self.elevenlabs_api_key:
            raise ValueError("ELEVENLABS_API_KEY not found. Set environment variable or use --tts-provider=polly")

        voice_config = self.elevenlabs_voices.get(speaker, self.elevenlabs_voices["expert"])

        try:
            response = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_config['id']}",
                headers={
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                    "xi-api-key": self.elevenlabs_api_key,
                },
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": voice_config["settings"],
                },
                timeout=120
            )
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"[!] ElevenLabs TTS failed: {e}")
            print(f"    Speaker: {speaker}, Voice: {voice_config['name']} ({voice_config['id']})")
            print(f"    Text length: {len(text)} chars")
            raise

    def _tts_polly(self, speaker: str, text: str) -> bytes:
        """
        Convert text to speech using AWS Polly
        """
        try:
            response = self.polly.synthesize_speech(
                Engine='neural',
                Text=text,
                OutputFormat='mp3',
                VoiceId=self.polly_voices[speaker]
            )

            if 'AudioStream' in response:
                return response['AudioStream'].read()
            else:
                print(f"[!] Polly response keys: {response.keys()}")
                raise KeyError("AudioStream not in Polly response")
        except Exception as e:
            print(f"[!] AWS Polly TTS failed: {e}")
            print(f"    Speaker: {speaker}, Voice: {self.polly_voices.get(speaker)}")
            print(f"    Text length: {len(text)} chars")
            raise

    def mix_audio(self, dialogue_script: List[Dict], output_path: str):
        """
        Generate and combine audio segments
        """
        try:
            from pydub import AudioSegment
            HAS_PYDUB = True
        except ImportError:
            print("[!]  pydub not installed. Skipping audio mixing.")
            print("   Install with: pip install pydub")
            HAS_PYDUB = False

        print("\n[4] Step 4: Generating audio...")

        # Fallback: Save individual MP3 files if pydub/ffmpeg not available
        if not HAS_PYDUB:
            return self._save_individual_audio_files(dialogue_script, output_path)

        try:
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
            print(f"\n[+] Audio saved to: {output_path}")
            print(f"   Duration: {len(combined) / 1000:.1f} seconds")

            return output_path

        except (FileNotFoundError, OSError) as e:
            # ffmpeg not found or pydub error - fall back to individual files
            print(f"\n[!] Audio mixing failed (ffmpeg not found): {e}")
            print("[!] Falling back to individual MP3 files...")
            return self._save_individual_audio_files(dialogue_script, output_path)

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
        print(f"\n[*] Dialogue script saved to: {script_path}")

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
            print("\n[!]  Dialogue not approved by quality gates. Skipping audio generation.")
            return {
                "success": False,
                "script_path": script_path,
                "certificate": cert
            }


def main():
    parser = argparse.ArgumentParser(description='Generate MIMO podcast dialogue from blog post')
    parser.add_argument('--blog-post', required=True, help='Path to MDX blog post')
    parser.add_argument('--output', required=True, help='Output MP3 path')
    parser.add_argument('--provider', default='xiami', help='LLM provider: mimo or xiami (default: xiami)')
    parser.add_argument('--tts-provider', default='elevenlabs', help='TTS provider: elevenlabs or polly (default: elevenlabs)')

    args = parser.parse_args()

    # Initialize agent (P18 v3.0 - credentials from environment)
    agent = PodcastMIMOAgent(provider=args.provider, tts_provider=args.tts_provider)

    # Generate podcast
    result = agent.generate_podcast(args.blog_post, args.output)

    if result['success']:
        print("\n[OK] SUCCESS! Dialogue podcast generated.")
        sys.exit(0)
    else:
        print("\n[-] Quality gates failed. Check script for issues.")
        sys.exit(1)


if __name__ == '__main__':
    main()
