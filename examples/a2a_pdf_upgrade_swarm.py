#!/usr/bin/env python3
"""
A2A PDF Upgrade Advisor Swarm - Reader → Analyzer → Advisor

Three-agent certified swarm for reading PDFs and generating upgrade suggestions.

Pipeline:
1. Reader Agent: Extracts text from PDFs in specified folder
2. Analyzer Agent: Analyzes content to identify components/versions
3. Advisor Agent: Generates prioritized upgrade recommendations

Prerequisites:
    pip install pypdf openai httpx

    # Start sidecar (for RSCT engine)
    cd sidecar && docker-compose up -d

    # Set API key
    export OPENAI_API_KEY=sk-...

Usage:
    PYTHONPATH=/path/to/swarm-it python examples/a2a_pdf_upgrade_swarm.py

    # Or with custom folder:
    PYTHONPATH=/path/to/swarm-it python examples/a2a_pdf_upgrade_swarm.py /path/to/pdfs
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sidecar.a2a import SwarmCertifier, Agent, AgentRole

# PDF extraction
try:
    from pypdf import PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        PdfReader = None
        print("Warning: Install pypdf or PyPDF2 for PDF extraction: pip install pypdf")

# OpenAI for LLM calls
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
    print("Warning: Install openai for LLM analysis: pip install openai")


@dataclass
class PDFDocument:
    """Extracted PDF document."""
    filename: str
    content: str
    page_count: int
    extraction_error: Optional[str] = None


@dataclass
class UpgradeSuggestion:
    """Single upgrade recommendation."""
    priority: str  # CRITICAL, HIGH, MEDIUM, LOW
    component: str
    current_version: Optional[str]
    suggested_version: Optional[str]
    reason: str
    risk_if_ignored: str


class PDFReaderAgent:
    """Agent 1: Reads and extracts content from PDFs."""

    def __init__(self, agent: Agent, certifier: SwarmCertifier):
        self.agent = agent
        self.certifier = certifier

    def read_pdfs(self, folder: str, swarm, source_id: str) -> Dict[str, Any]:
        """
        Read all PDFs from folder with certification.

        Args:
            folder: Path to folder containing PDFs
            swarm: Swarm instance
            source_id: ID of requesting agent

        Returns:
            Dict with certification and extracted documents
        """
        # Certify the read request
        msg = self.certifier.certify_message(
            swarm,
            source_id=source_id,
            target_id=self.agent.id,
            content=f"Extract text content from PDF files in folder: {folder}"
        )

        result = {
            "cert": {
                "R": msg.R,
                "S": msg.S,
                "N": msg.N,
                "kappa": msg.kappa,
                "allowed": msg.allowed,
                "decision": msg.decision,
            },
            "documents": [],
            "blocked": not msg.allowed,
            "folder": folder,
        }

        if not msg.allowed:
            result["error"] = f"Request blocked: {msg.decision}"
            return result

        # Extract PDFs
        pdf_folder = Path(folder)
        if not pdf_folder.exists():
            result["error"] = f"Folder not found: {folder}"
            return result

        pdf_files = list(pdf_folder.glob("*.pdf"))
        if not pdf_files:
            result["error"] = f"No PDF files found in {folder}"
            return result

        for pdf_path in pdf_files:
            doc = self._extract_pdf(pdf_path)
            result["documents"].append(doc)

        return result

    def _extract_pdf(self, pdf_path: Path) -> PDFDocument:
        """Extract text from a single PDF."""
        if PdfReader is None:
            return PDFDocument(
                filename=pdf_path.name,
                content=f"[PDF extraction unavailable - install pypdf]",
                page_count=0,
                extraction_error="pypdf not installed"
            )

        try:
            reader = PdfReader(str(pdf_path))
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)

            return PDFDocument(
                filename=pdf_path.name,
                content="\n\n---PAGE BREAK---\n\n".join(pages),
                page_count=len(reader.pages),
            )
        except Exception as e:
            return PDFDocument(
                filename=pdf_path.name,
                content="",
                page_count=0,
                extraction_error=str(e)
            )


class AnalyzerAgent:
    """Agent 2: Analyzes PDF content to identify components and versions."""

    def __init__(self, agent: Agent, certifier: SwarmCertifier, openai_client: Optional["OpenAI"] = None):
        self.agent = agent
        self.certifier = certifier
        self.client = openai_client

    def analyze(self, documents: List[PDFDocument], swarm, source_id: str) -> Dict[str, Any]:
        """
        Analyze documents to identify software components/versions.

        Args:
            documents: List of extracted PDF documents
            swarm: Swarm instance
            source_id: ID of requesting agent

        Returns:
            Dict with certification and analysis results
        """
        # Build context for certification
        doc_summaries = []
        for doc in documents:
            preview = doc.content[:500] if doc.content else "[empty]"
            doc_summaries.append(f"- {doc.filename} ({doc.page_count} pages): {preview}...")

        context = f"Analyzing {len(documents)} documents for upgrade opportunities:\n" + "\n".join(doc_summaries)

        # Certify the analysis request
        msg = self.certifier.certify_message(
            swarm,
            source_id=source_id,
            target_id=self.agent.id,
            content=context[:2000]  # Truncate for certification
        )

        result = {
            "cert": {
                "R": msg.R,
                "S": msg.S,
                "N": msg.N,
                "kappa": msg.kappa,
                "allowed": msg.allowed,
                "decision": msg.decision,
            },
            "analysis": None,
            "blocked": not msg.allowed,
        }

        if not msg.allowed:
            result["error"] = f"Analysis blocked: {msg.decision}"
            return result

        # Perform analysis
        if self.client:
            result["analysis"] = self._llm_analyze(documents)
        else:
            result["analysis"] = self._rule_based_analyze(documents)

        return result

    def _llm_analyze(self, documents: List[PDFDocument]) -> Dict[str, Any]:
        """Use LLM to analyze documents."""
        # Combine document content (truncated for context window)
        combined_content = ""
        for doc in documents:
            combined_content += f"\n\n=== {doc.filename} ===\n"
            combined_content += doc.content[:3000]  # Limit per document

        prompt = f"""Analyze the following technical documents and identify:
1. Software components mentioned (libraries, frameworks, tools)
2. Version numbers if specified
3. Potential areas that may need upgrades
4. Any security-related mentions
5. Dependencies and their relationships

Documents:
{combined_content[:12000]}

Respond in JSON format:
{{
    "components": [
        {{"name": "...", "version": "...", "category": "library|framework|tool|database|os"}},
    ],
    "security_mentions": ["..."],
    "upgrade_candidates": ["..."],
    "dependencies": {{"component": ["depends_on", ...]}}
}}"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            import json
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {
                "error": str(e),
                "components": [],
                "security_mentions": [],
                "upgrade_candidates": [],
            }

    def _rule_based_analyze(self, documents: List[PDFDocument]) -> Dict[str, Any]:
        """Simple rule-based analysis when LLM unavailable."""
        import re

        components = []
        version_pattern = r'(\b(?:v|version\s*)?\d+\.\d+(?:\.\d+)?(?:-\w+)?)\b'

        # Common software patterns
        software_patterns = {
            "Python": r'\bPython\s*(\d+\.\d+(?:\.\d+)?)?',
            "Node.js": r'\bNode(?:\.js)?\s*(\d+\.\d+(?:\.\d+)?)?',
            "React": r'\bReact\s*(\d+\.\d+(?:\.\d+)?)?',
            "Django": r'\bDjango\s*(\d+\.\d+(?:\.\d+)?)?',
            "PostgreSQL": r'\bPostgreSQL?\s*(\d+(?:\.\d+)?)?',
            "Docker": r'\bDocker\s*(\d+\.\d+(?:\.\d+)?)?',
            "Kubernetes": r'\bKubernetes\s*(\d+\.\d+(?:\.\d+)?)?',
            "AWS": r'\bAWS\b',
            "Java": r'\bJava\s*(\d+)?',
            "Spring": r'\bSpring(?:\s*Boot)?\s*(\d+\.\d+(?:\.\d+)?)?',
        }

        for doc in documents:
            content = doc.content
            for name, pattern in software_patterns.items():
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    version = matches[0] if matches[0] else None
                    if not any(c["name"] == name for c in components):
                        components.append({
                            "name": name,
                            "version": version,
                            "category": "framework" if name in ["React", "Django", "Spring"] else "tool",
                            "source": doc.filename,
                        })

        return {
            "components": components,
            "security_mentions": [],
            "upgrade_candidates": [c["name"] for c in components if c.get("version")],
            "analysis_method": "rule_based",
        }


class AdvisorAgent:
    """Agent 3: Generates prioritized upgrade recommendations."""

    def __init__(self, agent: Agent, certifier: SwarmCertifier, openai_client: Optional["OpenAI"] = None):
        self.agent = agent
        self.certifier = certifier
        self.client = openai_client

    def suggest_upgrades(self, analysis: Dict[str, Any], swarm, source_id: str) -> Dict[str, Any]:
        """
        Generate upgrade suggestions based on analysis.

        Args:
            analysis: Analysis results from AnalyzerAgent
            swarm: Swarm instance
            source_id: ID of requesting agent

        Returns:
            Dict with certification and upgrade suggestions
        """
        # Certify the advisory request
        content = f"Generate upgrade suggestions for: {analysis}"
        msg = self.certifier.certify_message(
            swarm,
            source_id=source_id,
            target_id=self.agent.id,
            content=str(content)[:2000]
        )

        result = {
            "cert": {
                "R": msg.R,
                "S": msg.S,
                "N": msg.N,
                "kappa": msg.kappa,
                "allowed": msg.allowed,
                "decision": msg.decision,
            },
            "suggestions": [],
            "blocked": not msg.allowed,
        }

        if not msg.allowed:
            result["error"] = f"Advisory blocked: {msg.decision}"
            return result

        # Generate suggestions
        if self.client:
            result["suggestions"] = self._llm_suggest(analysis)
        else:
            result["suggestions"] = self._rule_based_suggest(analysis)

        return result

    def _llm_suggest(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Use LLM to generate upgrade suggestions."""
        import json

        prompt = f"""Based on this software analysis, provide upgrade recommendations:

Analysis:
{json.dumps(analysis, indent=2)}

For each component that needs attention, provide:
1. Priority (CRITICAL, HIGH, MEDIUM, LOW)
2. Current version (if known)
3. Suggested target version (research latest stable)
4. Reason for upgrade
5. Risk if ignored

Respond in JSON format:
{{
    "suggestions": [
        {{
            "priority": "HIGH",
            "component": "...",
            "current_version": "...",
            "suggested_version": "...",
            "reason": "...",
            "risk_if_ignored": "..."
        }}
    ],
    "summary": "Brief overall assessment"
}}"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content)
            return data.get("suggestions", [])
        except Exception as e:
            return [{
                "priority": "UNKNOWN",
                "component": "Error",
                "reason": str(e),
                "risk_if_ignored": "Unable to assess",
            }]

    def _rule_based_suggest(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Simple rule-based suggestions when LLM unavailable."""
        suggestions = []

        # Known version recommendations (simplified)
        latest_versions = {
            "Python": ("3.12", "Security patches, performance improvements"),
            "Node.js": ("20.x LTS", "Long-term support, security updates"),
            "React": ("18.x", "Concurrent features, automatic batching"),
            "Django": ("5.0", "Security updates, async improvements"),
            "PostgreSQL": ("16", "Performance, security enhancements"),
            "Java": ("21 LTS", "Virtual threads, pattern matching"),
        }

        components = analysis.get("components", [])
        for comp in components:
            name = comp.get("name")
            current = comp.get("version")

            if name in latest_versions:
                suggested, reason = latest_versions[name]
                suggestions.append({
                    "priority": "HIGH" if name in ["Python", "Java", "Node.js"] else "MEDIUM",
                    "component": name,
                    "current_version": current,
                    "suggested_version": suggested,
                    "reason": reason,
                    "risk_if_ignored": "Potential security vulnerabilities, missing features",
                })

        # Add generic suggestion if no specific matches
        if not suggestions and components:
            suggestions.append({
                "priority": "LOW",
                "component": "General",
                "current_version": None,
                "suggested_version": None,
                "reason": "Review all components for latest stable versions",
                "risk_if_ignored": "Gradual technical debt accumulation",
            })

        return suggestions


def print_separator(title: str = ""):
    """Print a visual separator."""
    if title:
        print(f"\n{'='*70}")
        print(f" {title}")
        print('='*70)
    else:
        print('-'*70)


def print_cert(cert: Dict[str, Any], prefix: str = "  "):
    """Print certification details."""
    status = "✓ ALLOWED" if cert["allowed"] else "✗ BLOCKED"
    color = '\033[92m' if cert["allowed"] else '\033[91m'
    reset = '\033[0m'
    print(f"{prefix}{color}R={cert['R']:.2f} S={cert['S']:.2f} N={cert['N']:.2f} κ={cert['kappa']:.2f} → {status}{reset}")


def run_pipeline(pdf_folder: str, certifier: SwarmCertifier, swarm, reader, analyzer, advisor):
    """Run the full PDF analysis pipeline."""

    print_separator("STEP 1: PDF EXTRACTION")
    print(f"Folder: {pdf_folder}\n")

    # Step 1: Read PDFs
    read_result = reader.read_pdfs(pdf_folder, swarm, source_id="user")
    print("READER AGENT:")
    print_cert(read_result["cert"])

    if read_result["blocked"]:
        print(f"  ✗ Pipeline stopped: {read_result.get('error', 'blocked')}")
        return None

    if "error" in read_result:
        print(f"  ✗ Error: {read_result['error']}")
        return None

    docs = read_result["documents"]
    print(f"  Extracted {len(docs)} documents:")
    for doc in docs:
        status = "✓" if not doc.extraction_error else f"⚠ {doc.extraction_error}"
        print(f"    - {doc.filename} ({doc.page_count} pages) {status}")

    # Step 2: Analyze
    print_separator("STEP 2: CONTENT ANALYSIS")

    analysis_result = analyzer.analyze(docs, swarm, source_id="reader")
    print("ANALYZER AGENT:")
    print_cert(analysis_result["cert"])

    if analysis_result["blocked"]:
        print(f"  ✗ Pipeline stopped: analysis blocked")
        return None

    analysis = analysis_result["analysis"]
    if analysis:
        components = analysis.get("components", [])
        print(f"\n  Found {len(components)} components:")
        for comp in components[:10]:  # Limit display
            version = comp.get("version", "unknown")
            print(f"    - {comp['name']}: v{version}")

        if len(components) > 10:
            print(f"    ... and {len(components) - 10} more")

    # Step 3: Generate suggestions
    print_separator("STEP 3: UPGRADE RECOMMENDATIONS")

    suggest_result = advisor.suggest_upgrades(analysis, swarm, source_id="analyzer")
    print("ADVISOR AGENT:")
    print_cert(suggest_result["cert"])

    if suggest_result["blocked"]:
        print(f"  ✗ Pipeline stopped: advisory blocked")
        return None

    suggestions = suggest_result["suggestions"]
    print(f"\n  Generated {len(suggestions)} recommendations:\n")

    # Sort by priority
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "UNKNOWN": 4}
    suggestions.sort(key=lambda x: priority_order.get(x.get("priority", "UNKNOWN"), 5))

    for s in suggestions:
        priority = s.get("priority", "?")
        color = {
            "CRITICAL": '\033[91m',  # Red
            "HIGH": '\033[93m',      # Yellow
            "MEDIUM": '\033[94m',    # Blue
            "LOW": '\033[90m',       # Gray
        }.get(priority, '\033[0m')
        reset = '\033[0m'

        print(f"  {color}[{priority}]{reset} {s.get('component', 'Unknown')}")
        if s.get("current_version"):
            print(f"         Current: {s['current_version']} → Suggested: {s.get('suggested_version', 'latest')}")
        print(f"         Reason: {s.get('reason', 'N/A')}")
        print(f"         Risk: {s.get('risk_if_ignored', 'N/A')}")
        print()

    return {
        "documents": docs,
        "analysis": analysis,
        "suggestions": suggestions,
    }


def main():
    print_separator("A2A PDF UPGRADE ADVISOR SWARM")

    # Get PDF folder from args or use default
    pdf_folder = sys.argv[1] if len(sys.argv) > 1 else "ram_pdfs"

    # Check for OpenAI
    openai_client = None
    if OpenAI and os.getenv("OPENAI_API_KEY"):
        openai_client = OpenAI()
        print("✓ OpenAI client initialized (LLM analysis enabled)")
    else:
        print("⚠ OpenAI not configured (using rule-based analysis)")
        print("  Set OPENAI_API_KEY for better results")

    print()

    # Initialize certifier
    certifier = SwarmCertifier()

    # Define agents
    user = Agent(id="user", name="User", role=AgentRole.COORDINATOR)
    reader = Agent(id="reader", name="PDF Reader", role=AgentRole.SPECIALIST)
    analyzer = Agent(id="analyzer", name="Content Analyzer", role=AgentRole.WORKER)
    advisor = Agent(id="advisor", name="Upgrade Advisor", role=AgentRole.VALIDATOR)

    # Create swarm
    swarm = certifier.create_swarm("pdf-upgrade-swarm", [user, reader, analyzer, advisor])

    # Define communication topology: user → reader → analyzer → advisor → user
    certifier.add_link(swarm, "user", "reader")
    certifier.add_link(swarm, "reader", "analyzer")
    certifier.add_link(swarm, "analyzer", "advisor")
    certifier.add_link(swarm, "advisor", "user")

    print("Swarm topology: user → reader → analyzer → advisor")
    print_separator()

    # Create agent instances
    pdf_reader = PDFReaderAgent(reader, certifier)
    pdf_analyzer = AnalyzerAgent(analyzer, certifier, openai_client)
    upgrade_advisor = AdvisorAgent(advisor, certifier, openai_client)

    # Run pipeline
    result = run_pipeline(pdf_folder, certifier, swarm, pdf_reader, pdf_analyzer, upgrade_advisor)

    # Swarm certificate
    print_separator("SWARM CERTIFICATE")

    cert = certifier.get_swarm_certificate(swarm)
    print(f"\n  Swarm ID: {cert.swarm_id}")
    print(f"  Total messages: {cert.total_messages}")
    print(f"  kappa_swarm: {cert.kappa_swarm:.2f}")

    health_color = '\033[92m' if cert.swarm_healthy else '\033[91m'
    reset = '\033[0m'
    print(f"  Swarm healthy: {health_color}{cert.swarm_healthy}{reset}")

    print("\n  Link health:")
    for link_id, kappa in cert.link_kappas.items():
        marker = "✓" if kappa >= 0.5 else "⚠"
        print(f"    {marker} {link_id}: κ={kappa:.2f}")

    if cert.weakest_link_id:
        print(f"\n  Weakest link: {cert.weakest_link_id}")

    if cert.issues:
        print("\n  Issues:")
        for issue in cert.issues:
            print(f"    ⚠ {issue}")

    print_separator()

    # Return result for programmatic use
    return result


if __name__ == "__main__":
    main()
