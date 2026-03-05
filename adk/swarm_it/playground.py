"""
Interactive Playground - Phase 5 Developer Experience

Streamlit-based interactive playground for RSCT certification:
- Live certification testing
- Domain presets (medical, legal, financial, research, dev)
- Threshold sliders
- Real-time results visualization
- Evidence export

Based on APIDesigner recommendation (kappa=0.308):
"Interactive playground would significantly improve developer onboarding
and experimentation."

Implements:
- Streamlit UI
- Domain-specific presets
- Real-time certification
- Results visualization
- Evidence export

Usage:
    streamlit run playground.py
"""

from typing import Optional, Dict, Any
import sys
from pathlib import Path

try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

# Ensure swarm_it is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from swarm_it.fluent import FluentCertifier
from swarm_it.validation import CertificationDomain


# Domain presets matching fluent.py
DOMAIN_PRESETS = {
    "medical": {
        "kappa": 0.9,
        "R": 0.5,
        "S": 0.6,
        "N": 0.3,
        "description": "Medical domain (strict quality requirements)"
    },
    "legal": {
        "kappa": 0.85,
        "R": 0.5,
        "S": 0.5,
        "N": 0.4,
        "description": "Legal domain (strict quality requirements)"
    },
    "financial": {
        "kappa": 0.8,
        "R": 0.45,
        "S": 0.45,
        "N": 0.4,
        "description": "Financial domain (moderate quality requirements)"
    },
    "research": {
        "kappa": 0.7,
        "R": 0.3,
        "S": 0.4,
        "N": 0.5,
        "description": "Research domain (moderate quality requirements)"
    },
    "dev": {
        "kappa": 0.5,
        "R": 0.2,
        "S": 0.2,
        "N": 0.7,
        "description": "Development domain (permissive requirements)"
    },
    "custom": {
        "kappa": 0.7,
        "R": 0.3,
        "S": 0.4,
        "N": 0.3,
        "description": "Custom thresholds"
    }
}


def render_sidebar():
    """Render configuration sidebar."""
    st.sidebar.title("RSCT Configuration")

    # Domain selection
    domain = st.sidebar.selectbox(
        "Domain",
        options=list(DOMAIN_PRESETS.keys()),
        index=3,  # Default to "research"
        help="Select certification domain or 'custom' for manual configuration"
    )

    preset = DOMAIN_PRESETS[domain]
    st.sidebar.info(preset["description"])

    # Threshold configuration
    st.sidebar.subheader("Quality Thresholds")

    if domain == "custom":
        kappa = st.sidebar.slider(
            "Kappa (κ) - Compatibility",
            min_value=0.0,
            max_value=1.0,
            value=preset["kappa"],
            step=0.05,
            help="Minimum compatibility score"
        )
        R = st.sidebar.slider(
            "R - Relevance",
            min_value=0.0,
            max_value=1.0,
            value=preset["R"],
            step=0.05,
            help="Minimum relevance score"
        )
        S = st.sidebar.slider(
            "S - Stability",
            min_value=0.0,
            max_value=1.0,
            value=preset["S"],
            step=0.05,
            help="Minimum stability score"
        )
        N = st.sidebar.slider(
            "N - Noise",
            min_value=0.0,
            max_value=1.0,
            value=preset["N"],
            step=0.05,
            help="Maximum noise score"
        )
    else:
        kappa = preset["kappa"]
        R = preset["R"]
        S = preset["S"]
        N = preset["N"]

        # Display preset values
        st.sidebar.metric("Kappa (κ)", f"{kappa:.2f}")
        st.sidebar.metric("R (Relevance)", f"{R:.2f}")
        st.sidebar.metric("S (Stability)", f"{S:.2f}")
        st.sidebar.metric("N (Noise)", f"{N:.2f}")

    # Advanced options
    st.sidebar.subheader("Advanced Options")

    enable_caching = st.sidebar.checkbox(
        "Enable Caching",
        value=False,
        help="Enable Redis caching for faster responses"
    )

    enable_tracing = st.sidebar.checkbox(
        "Enable Tracing",
        value=False,
        help="Enable OpenTelemetry distributed tracing"
    )

    enable_monitoring = st.sidebar.checkbox(
        "Enable Monitoring",
        value=False,
        help="Enable Prometheus metrics collection"
    )

    enable_audit = st.sidebar.checkbox(
        "Enable Audit Logging",
        value=False,
        help="Enable SR 11-7 compliant audit logging"
    )

    export_evidence = st.sidebar.checkbox(
        "Export Evidence",
        value=False,
        help="Export certification evidence to file"
    )

    return {
        "domain": domain,
        "kappa": kappa,
        "R": R,
        "S": S,
        "N": N,
        "enable_caching": enable_caching,
        "enable_tracing": enable_tracing,
        "enable_monitoring": enable_monitoring,
        "enable_audit": enable_audit,
        "export_evidence": export_evidence
    }


def render_main_content(config: Dict[str, Any]):
    """Render main content area."""
    st.title("RSCT Interactive Playground")
    st.markdown("""
    Test **Rotor-based Self-Certifying Thought (RSCT)** certification in real-time.

    Configure quality thresholds in the sidebar, enter your prompt below, and click **Certify** to see results.
    """)

    # Prompt input
    prompt = st.text_area(
        "Prompt",
        height=200,
        placeholder="Enter the prompt you want to certify...",
        help="Enter the text you want to certify (10-100,000 characters)"
    )

    # User context (optional)
    with st.expander("User Context (Optional)"):
        col1, col2 = st.columns(2)
        with col1:
            user_id = st.text_input("User ID", help="Optional user ID for audit trail")
        with col2:
            org_id = st.text_input("Organization ID", help="Optional org ID for audit trail")

    # Certify button
    if st.button("Certify", type="primary", use_container_width=True):
        if not prompt or len(prompt) < 10:
            st.error("Prompt must be at least 10 characters long")
            return

        if len(prompt) > 100000:
            st.error("Prompt must be less than 100,000 characters")
            return

        # Build certifier
        with st.spinner("Running certification..."):
            try:
                certifier = FluentCertifier()
                certifier = certifier.with_prompt(prompt)
                certifier = certifier.for_domain(config["domain"] if config["domain"] != "custom" else "research")
                certifier = certifier.with_thresholds(
                    kappa=config["kappa"],
                    R=config["R"],
                    S=config["S"],
                    N=config["N"]
                )

                if user_id:
                    certifier = certifier.with_user(user_id)
                if org_id:
                    certifier = certifier.with_org(org_id)

                if config["enable_caching"]:
                    certifier = certifier.enable_caching()
                if config["enable_tracing"]:
                    certifier = certifier.enable_tracing()
                if config["enable_monitoring"]:
                    certifier = certifier.enable_monitoring()
                if config["enable_audit"]:
                    certifier = certifier.enable_audit()
                if config["export_evidence"]:
                    certifier = certifier.export_evidence()

                # Execute certification
                result = certifier.certify()

                # Display results
                render_results(result, config)

            except Exception as e:
                st.error(f"Certification failed: {str(e)}")
                if hasattr(e, 'guidance'):
                    st.info(f"Guidance: {e.guidance}")


def render_results(result: Dict[str, Any], config: Dict[str, Any]):
    """Render certification results."""
    st.subheader("Certification Results")

    # Decision
    decision = result.get("decision", "UNKNOWN")
    if decision == "EXECUTE":
        st.success(f"Decision: {decision}")
    else:
        st.error(f"Decision: {decision}")

    # Quality metrics
    st.subheader("Quality Metrics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        kappa = result.get("kappa", 0.0)
        kappa_threshold = config["kappa"]
        st.metric(
            "Kappa (κ)",
            f"{kappa:.3f}",
            delta=f"{kappa - kappa_threshold:+.3f}",
            delta_color="normal" if kappa >= kappa_threshold else "inverse"
        )

    with col2:
        R = result.get("R", 0.0)
        R_threshold = config["R"]
        st.metric(
            "Relevance (R)",
            f"{R:.3f}",
            delta=f"{R - R_threshold:+.3f}",
            delta_color="normal" if R >= R_threshold else "inverse"
        )

    with col3:
        S = result.get("S", 0.0)
        S_threshold = config["S"]
        st.metric(
            "Stability (S)",
            f"{S:.3f}",
            delta=f"{S - S_threshold:+.3f}",
            delta_color="normal" if S >= S_threshold else "inverse"
        )

    with col4:
        N = result.get("N", 0.0)
        N_threshold = config["N"]
        st.metric(
            "Noise (N)",
            f"{N:.3f}",
            delta=f"{N - N_threshold:+.3f}",
            delta_color="inverse" if N <= N_threshold else "normal"
        )

    # Gate results
    if "gate_results" in result:
        st.subheader("Quality Gates")
        gates = result["gate_results"]

        for gate_name, gate_result in gates.items():
            passed = gate_result.get("passed", False)
            icon = "✓" if passed else "✗"
            color = "green" if passed else "red"
            st.markdown(f":{color}[{icon}] **{gate_name}**: {gate_result.get('message', '')}")

    # Evidence
    if "evidence" in result:
        with st.expander("View Evidence"):
            st.json(result["evidence"])

    # Full result
    with st.expander("View Full Result"):
        st.json(result)


def main():
    """Main entry point."""
    if not STREAMLIT_AVAILABLE:
        print("Streamlit not installed. Install with: pip install streamlit")
        sys.exit(1)

    # Page config
    st.set_page_config(
        page_title="RSCT Playground",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Render UI
    config = render_sidebar()
    render_main_content(config)

    # Footer
    st.markdown("---")
    st.markdown("""
    **RSCT Framework**: Rotor-based Self-Certifying Thought

    - **R** (Relevance): How well the output addresses the prompt
    - **S** (Stability): Consistency and coherence of the output
    - **N** (Noise): Irrelevant or low-quality content
    - **κ** (Kappa): Compatibility score (min of R and S)

    **Constraint**: R + S + N = 1.0 (simplex)
    """)


if __name__ == "__main__":
    main()
