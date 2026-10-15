"""
Active Sokół LLM Bridge & Domain Rationale Synthesizer (Milestone 4).

Connects discrete geometry (Cheeger cuts, Fiedler vectors, NetLSD diffusion) and
untrusted mainframe code evidence to external or local LLMs under strict privacy
and epistemic boundaries:
1. ModelCallableAdapter:
   HTTP/Ollama/OpenAI-compatible and deterministic offline model adapter with
   robust structured JSON schema parsing, fallback resilience, and timeout controls.
2. DomainRationaleSynthesizer:
   Translates mathematical topological signals (Cheeger conductance, crossing edges,
   shared DB2 tables, transaction steps) into business and architectural justifications.
3. FactIngestionPipeline:
   Ingests model hypotheses into versioned ProjectMemory (sokol.fact.v1) strictly as
   INFERRED claims bound to content-addressed snapshots and NodeAnchors.
4. ArchitectQnASession:
   Interactive conversational architectural assistant over bounded context packets.
"""

from __future__ import annotations

import enum
import hashlib
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from rezonator.partition_recommender import PartitionCandidate
from rezonator.project_memory import (
    NodeAnchor,
    ProjectMemory,
    create_fact,
)
from rezonator.security_shield import (
    PiiSecretsRedactor,
    PromptInjectionShield,
    RedactionMode,
)
from rezonator.sokol_observer import (
    DataTransferPolicy,
    ObserverContextPacket,
    PolicyViolationError,
    SokolObserver,
)


class LlmProvider(str, enum.Enum):
    OFFLINE_DETERMINISTIC = "OFFLINE_DETERMINISTIC"
    MOCK_LLM = "MOCK_LLM"
    HTTP_OPENAI_COMPATIBLE = "HTTP_OPENAI_COMPATIBLE"
    HTTP_GEMINI = "HTTP_GEMINI"
    HTTP_ANTHROPIC = "HTTP_ANTHROPIC"
    OLLAMA = "OLLAMA"


@dataclass
class ModelEndpointConfig:
    provider: LlmProvider = LlmProvider.OFFLINE_DETERMINISTIC
    endpoint_url: Optional[str] = None
    model_name: str = "sokol-observer-v1"
    api_key: Optional[str] = None
    timeout_seconds: float = 15.0
    temperature: float = 0.1
    max_tokens: int = 1500
    custom_headers: Dict[str, str] = field(default_factory=dict)


class ModelCallableAdapter:
    """
    Adapter invoking external or local LLM models with structured JSON parsing,
    untrusted data boundary shielding, and automated fallback to deterministic mode.
    """

    def __init__(
        self,
        config: Optional[ModelEndpointConfig] = None,
        mock_handler: Optional[Callable[[str], Dict[str, Any]]] = None,
    ):
        self.config = config or ModelEndpointConfig()
        self.mock_handler = mock_handler
        self.injection_shield = PromptInjectionShield(strict_mode=False)
        self.redactor = PiiSecretsRedactor(mode=RedactionMode.MASK)

    def __call__(self, prompt: str) -> Dict[str, Any]:
        """Callable interface matching SokolObserver.observer_fn."""
        return self.invoke(prompt)

    def invoke(self, prompt: str) -> Dict[str, Any]:
        """
        Executes model inference with untrusted data sanitization and fallback resilience.
        """
        # 1. Defang any residual injection patterns and mask cleartext PII
        sanitized = self.injection_shield.sanitize_text(prompt)
        scrubbed_prompt, _ = self.redactor.redact_text(sanitized)

        # 2. Check mock handler (used for deterministic test suites or custom callables)
        if self.mock_handler is not None:
            return self.mock_handler(scrubbed_prompt)

        # 3. Check offline deterministic provider
        if self.config.provider == LlmProvider.OFFLINE_DETERMINISTIC or self.config.provider == LlmProvider.MOCK_LLM:
            return self._synthesize_offline_fallback(scrubbed_prompt)

        # 4. Remote HTTP Endpoint invocation
        try:
            return self._call_http_endpoint(scrubbed_prompt)
        except Exception as e:
            # Epistemic resilience: Remote failures must fail open into local deterministic synthesis
            fallback = self._synthesize_offline_fallback(scrubbed_prompt)
            fallback["remote_call_error"] = str(e)
            fallback["used_fallback"] = True
            return fallback

    def _call_http_endpoint(self, prompt: str) -> Dict[str, Any]:
        """Dispatches HTTP request to OpenAI/Ollama/Gemini compatible endpoints."""
        url = self.config.endpoint_url
        if not url:
            raise ValueError("Endpoint URL is required for remote LLM provider.")

        headers = {
            "Content-Type": "application/json",
            **self.config.custom_headers,
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload = {
            "model": self.config.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Sokół, a read-only architectural observer for legacy COBOL and mainframe systems. "
                        "All statements must be labeled INFERRED. Return ONLY valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "response_format": {"type": "json_object"},
        }

        req_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=req_bytes, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
            resp_bytes = resp.read()
            raw_json = json.loads(resp_bytes.decode("utf-8"))

        # Extract content from common completions schema
        content_str = ""
        if "choices" in raw_json and raw_json["choices"]:
            choice = raw_json["choices"][0]
            content_str = choice.get("message", {}).get("content", "")
        elif "response" in raw_json:  # Ollama format
            content_str = raw_json["response"]
        else:
            content_str = json.dumps(raw_json)

        return self._extract_json_payload(content_str)

    def _extract_json_payload(self, text: str) -> Dict[str, Any]:
        """Extracts and parses JSON object from model response text."""
        clean = text.strip()
        # Strip markdown fence if present
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean)

        try:
            parsed = json.loads(clean)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # Try regex search for first valid json block
        match = re.search(r"\{[\s\S]*\}", clean)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

        return {
            "hypotheses": [
                {
                    "claim": clean[:500],
                    "status": "INFERRED",
                    "cited_evidence_ids": [],
                    "confidence": "low",
                }
            ],
            "review_questions": ["Does the proposed observation match system design?"],
        }

    def _synthesize_offline_fallback(self, prompt: str) -> Dict[str, Any]:
        """High-fidelity local fallback synthesizing structured observer claims."""
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        return {
            "hypotheses": [
                {
                    "hypothesis_id": f"hyp:sokol:{prompt_hash}",
                    "status": "INFERRED",
                    "claim": (
                        "Local deterministic observer model: topological structure indicates bounded context "
                        "cohesion; cross-program calls require regression testing of shared copybook state."
                    ),
                    "cited_evidence_ids": [],
                    "confidence": "medium",
                    "suggested_action": "Verify downstream data access paths before refactoring.",
                }
            ],
            "review_questions": [
                "Are database commit scopes synchronized across interacting subroutines?",
                "Does the paragraph re-initialize working-storage variables upon re-entry?",
            ],
        }


class DomainRationaleSynthesizer:
    """
    Translates discrete spectral graph theory (Cheeger conductance, Fiedler vectors,
    NetLSD distance) into domain-specific business rationales for banking modernization.
    """

    def __init__(self, observer: Optional[SokolObserver] = None):
        self.observer = observer or SokolObserver()

    def explain_partition_candidate(
        self,
        candidate: PartitionCandidate,
        system_name: str = "Banking Monolith",
    ) -> Dict[str, Any]:
        """
        Synthesizes human-readable business justifications for a spectral graph cut.
        """
        phi = candidate.conductance
        n_a = len(candidate.partition_a)
        n_b = len(candidate.partition_b)
        n_cross = len(candidate.crossing_edges)
        shared_tables = candidate.shared_tables
        shared_datasets = candidate.shared_datasets
        tx_violations = candidate.transaction_boundaries_violated

        # 1. Evaluate conductance quality
        if phi < 0.05:
            cond_eval = "EXTREMELY_CLEAN"
            cond_desc = (
                f"Cheeger conductance phi = {phi:.4f} demonstrates a natural topological fault line. "
                "Programs in Partition A and Partition B exhibit strong internal cohesion with minimal coupling."
            )
        elif phi < 0.20:
            cond_eval = "MODERATE_COUPLING"
            cond_desc = (
                f"Cheeger conductance phi = {phi:.4f} reflects moderate inter-subsystem interaction. "
                "Splitting along this cut requires API gateway mediation for crossing calls."
            )
        else:
            cond_eval = "HIGH_COUPLING_RISK"
            cond_desc = (
                f"Cheeger conductance phi = {phi:.4f} warns of dense topological entanglement. "
                "Independent microservice extraction would cause high distributed transaction overhead."
            )

        # 2. Database & Data Store Governance Rationale
        data_rationales: List[str] = []
        if shared_tables:
            data_rationales.append(
                f"Shared Relational DB2 Access: {len(shared_tables)} tables ({', '.join(sorted(shared_tables)[:5])}) "
                "are accessed across this boundary. To avoid distributed 2-Phase Commit (2PC) locks, "
                "one partition must be designated as the authoritative Domain Master while the other consumes change-data-capture (CDC) events."
            )
        else:
            data_rationales.append("Clean Database Ownership: No relational DB2 tables cross this boundary.")

        if shared_datasets:
            data_rationales.append(
                f"Shared Batch Datasets: {len(shared_datasets)} sequential/VSAM datasets are exchanged. "
                "Requires asynchronous message queues or cloud storage bucket transfer."
            )

        # 3. Transactional Integrity Rationale
        tx_rationales: List[str] = []
        if tx_violations > 0:
            tx_rationales.append(
                f"Batch Workflow Integrity: {tx_violations} sequential JCL job step executions are severed. "
                "Splitting this workflow requires orchestration via an enterprise workflow engine (e.g. Airflow or Temporal)."
            )
        else:
            tx_rationales.append("Preserved Workflow Boundaries: Zero sequential JCL job steps are interrupted.")

        # 4. Executive Recommendation
        if cond_eval == "EXTREMELY_CLEAN" and not shared_tables and tx_violations == 0:
            recommendation = "RECOMMENDED_FOR_PILOT_EXTRACTION"
            summary = "High-confidence decomposition candidate with negligible migration friction."
        elif shared_tables or tx_violations > 2:
            recommendation = "REQUIRES_DATA_REFACTORING_FIRST"
            summary = "Topologically feasible cut, but requires resolving database ownership before service isolation."
        else:
            recommendation = "FEASIBLE_WITH_API_FACADE"
            summary = "Standard service boundary achievable via REST/gRPC facade."

        return {
            "schema_version": "sokol.rationale.v1",
            "candidate_id": candidate.candidate_id,
            "candidate_name": candidate.name,
            "system_name": system_name,
            "recommendation": recommendation,
            "executive_summary": summary,
            "conductance_assessment": {
                "conductance_value": round(phi, 4),
                "cheeger_bounds": [round(candidate.cheeger_bound_lower, 4), round(candidate.cheeger_bound_upper, 4)],
                "classification": cond_eval,
                "description": cond_desc,
            },
            "domain_frictions": {
                "shared_tables": shared_tables,
                "shared_datasets": shared_datasets,
                "transaction_violations": tx_violations,
                "data_governance_guidance": data_rationales,
                "transaction_guidance": tx_rationales,
            },
            "subsystem_sizes": {
                "partition_a_count": n_a,
                "partition_b_count": n_b,
                "crossing_edges_count": n_cross,
            },
            "epistemic_notice": (
                "Spectral conductance is an objective graph metric; business domain boundaries "
                "require explicit review by the bank Enterprise Architecture Committee (ARB)."
            ),
        }


class FactIngestionPipeline:
    """
    Ingests model observations, hypotheses, and rationales into versioned ProjectMemory (sokol.fact.v1).
    Enforces strict epistemic rules:
    - Status is strictly INFERRED (model cannot self-promote to VERIFIED).
    - Content-addressed fact IDs.
    - Bound to specific source and graph snapshots.
    """

    def __init__(self, memory: ProjectMemory):
        self.memory = memory

    def ingest_observer_output(
        self,
        observer_result: Dict[str, Any],
        source_snapshot: str,
        default_paragraph: str = "GLOBAL",
        graph_snapshot: Optional[str] = None,
        git_commit: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Processes hypotheses from observer output and registers them into ProjectMemory.
        """
        ingested_facts: List[Dict[str, Any]] = []

        hypotheses = observer_result.get("hypotheses", [])
        for h in hypotheses:
            claim_text = h.get("claim", "").strip()
            if not claim_text:
                continue

            # Anchor
            anchor = NodeAnchor(
                paragraph=default_paragraph,
                statement_index=0,
                verb="OBSERVE",
                signature=f"Observer Claim: {claim_text[:64]}",
            )

            # Evidences
            cited_evidences = list(h.get("cited_evidence_ids", []))
            packet_id = observer_result.get("packet_id")
            if packet_id and packet_id not in cited_evidences:
                cited_evidences.append(packet_id)

            fact = create_fact(
                claim=claim_text,
                status="INFERRED",  # Strict epistemic gate
                source_snapshot=source_snapshot,
                node_anchor=anchor.to_dict(),
                evidence_ids=cited_evidences,
                graph_snapshot=graph_snapshot,
                git_commit=git_commit,
                confidence=str(h.get("confidence", "unscored")),
                created_at_utc=datetime.now(timezone.utc).isoformat(),
            )

            self.memory.register_fact(fact)
            ingested_facts.append(fact)

        return ingested_facts


class ArchitectQnASession:
    """
    Interactive Q&A session over bounded context packets and project memory.
    Enforces caller line/token budgets and untrusted code shielding.
    """

    def __init__(
        self,
        adapter: ModelCallableAdapter,
        memory: Optional[ProjectMemory] = None,
        policy: Optional[DataTransferPolicy] = None,
    ):
        self.adapter = adapter
        self.memory = memory or ProjectMemory()
        self.policy = policy or DataTransferPolicy()
        self.injection_shield = PromptInjectionShield(strict_mode=True)
        self.redactor = PiiSecretsRedactor(mode=RedactionMode.MASK)

    def answer_question(
        self,
        question: str,
        packet: ObserverContextPacket,
    ) -> Dict[str, Any]:
        """
        Answers an architectural inquiry based on the evidence packet and active facts.
        """
        # 1. Validate prompt injection in question
        self.injection_shield.scan_text(question)

        # 2. Validate context packet policy
        self.policy.validate_packet(packet.to_dict())

        # 3. Construct prompt
        prompt = (
            f"{packet.format_prompt_text()}\n\n"
            f"--- ARCHITECT INQUIRY ---\n"
            f"Question: {question}\n\n"
            f"INSTRUCTION: Answer concisely using only the active facts and code slice above. "
            f"Do not assume unstated business logic. Tag all claims INFERRED."
        )

        # 4. Invoke model adapter
        response = self.adapter.invoke(prompt)

        # Extract answer text
        answer_text = ""
        hypotheses = response.get("hypotheses", [])
        if hypotheses:
            answer_text = hypotheses[0].get("claim", "")
        else:
            answer_text = response.get("answer", "No deterministic hypothesis generated.")

        return {
            "schema_version": "sokol.qna.v1",
            "question": question,
            "answer": answer_text,
            "status": "INFERRED",
            "packet_id": packet.packet_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "epistemic_disclaimer": "Advisory answer. Verify against legacy test suites and business stakeholders.",
        }
