"""
Originality Check Agent - Plagiarism detection and rewrite triggers.

Detects potential plagiarism via semantic similarity and n-gram matching.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.prompts.originality import ORIGINALITY_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class FlaggedPassage(BaseModel):
    """Single flagged passage."""
    passage_id: str = Field(..., description="Identifier for the passage")
    text: str = Field(..., description="The flagged text")
    matched_source: Dict[str, Any] = Field(..., description="Matched source information")
    similarity_score: float = Field(..., description="Similarity score 0-1")
    similarity_type: str = Field(..., description="Type: semantic or n-gram")
    risk_level: str = Field(..., description="HIGH, MEDIUM, or LOW")
    reason: str = Field(..., description="Why it was flagged")
    rewrite_required: bool = Field(..., description="Whether rewrite is required")
    suggested_action: str = Field("", description="Suggested rewrite or action")


class AcceptableSimilarity(BaseModel):
    """Similarity that is acceptable (not plagiarism)."""
    passage_id: str = Field(..., description="Identifier")
    text: str = Field(..., description="The text")
    similarity_score: float = Field(..., description="Score 0-1")
    reason_for_acceptance: str = Field(..., description="Why it's acceptable")
    exception_type: str = Field(..., description="Type of exception")


class OriginalityStatistics(BaseModel):
    """Originality check statistics."""
    total_sentences_checked: int = 0
    high_risk_flagged: int = 0
    medium_risk_flagged: int = 0
    low_risk_flagged: int = 0
    acceptable_matches: int = 0
    pass_threshold: bool = False


class OriginalityResult(BaseModel):
    """Complete originality check output."""
    overall_originality_score: float = Field(..., description="0-1, higher = more original")
    flagged_passages: List[FlaggedPassage] = Field(default_factory=list)
    acceptable_similarities: List[AcceptableSimilarity] = Field(default_factory=list)
    statistics: OriginalityStatistics = Field(default_factory=OriginalityStatistics)
    recommendation: str = Field(..., description="APPROVED or REVISION_REQUIRED")
    revision_notes: str = Field("", description="Notes for revision")
    specific_rewrites_needed: List[str] = Field(default_factory=list)


class OriginalityAgent:
    """Originality check agent for plagiarism detection."""
    
    # Thresholds
    HIGH_RISK_THRESHOLD = 0.85
    MEDIUM_RISK_THRESHOLD = 0.75
    LOW_RISK_THRESHOLD = 0.65
    PASS_THRESHOLD = 0.85
    
    def __init__(self, llm_client, embedding_service=None):
        """
        Initialize Originality Agent.
        
        Args:
            llm_client: LLM client
            embedding_service: Service for computing embeddings (optional)
        """
        self.llm = llm_client
        self.embedding_service = embedding_service
    
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check report for originality issues.
        
        Args:
            state: Workflow state with draft report and source chunks
            
        Returns:
            Updated state with originality check results
        """
        logger.info("Originality Check Agent executing...")
        
        try:
            draft_report = state.get("draft_report")
            search_results = state.get("search_results", [])
            
            if not draft_report:
                logger.warning("No draft report to check")
                return {
                    "originality_check": None,
                    "current_stage": "originality_skipped"
                }
            
            # Extract report content
            main_content = draft_report.get("main_content", "")
            
            if not main_content:
                logger.warning("Draft report has no content")
                return {
                    "originality_check": None,
                    "current_stage": "originality_skipped"
                }
            
            # Extract source chunks
            source_chunks = self._extract_source_chunks(search_results)
            
            if not source_chunks:
                logger.info("No source chunks to compare against, assuming original")
                return {
                    "originality_check": {
                        "overall_originality_score": 1.0,
                        "recommendation": "APPROVED",
                        "flagged_passages": [],
                        "statistics": {"pass_threshold": True}
                    },
                    "current_stage": "originality_approved"
                }
            
            # Perform originality check
            result = await self._check_originality(main_content, source_chunks)
            
            logger.info(f"Originality check complete: score={result.overall_originality_score:.2f}, "
                       f"HIGH risk={result.statistics.high_risk_flagged}, "
                       f"recommendation={result.recommendation}")
            
            return {
                "originality_check": result.dict(),
                "current_stage": "originality_complete",
                "originality_passed": result.recommendation == "APPROVED"
            }
            
        except Exception as exc:
            logger.error(f"Originality Check Agent failed: {exc}", exc_info=True)
            # Default to requiring review on error
            return {
                "originality_check": {
                    "overall_originality_score": 0.0,
                    "recommendation": "REVISION_REQUIRED",
                    "revision_notes": f"Originality check failed: {str(exc)}"
                },
                "current_stage": "originality_failed",
                "errors": [f"Originality check failed: {str(exc)}"]
            }
    
    def _extract_source_chunks(self, search_results: List[Dict]) -> List[Dict[str, str]]:
        """Extract source text chunks from search results."""
        chunks = []
        
        for result in search_results:
            retrieved_chunks = result.get("retrieved_chunks", [])
            for chunk in retrieved_chunks:
                chunks.append({
                    "content": chunk.get("content", ""),
                    "source": chunk.get("source", ""),
                    "source_type": chunk.get("source_type", ""),
                    "source_id": chunk.get("source_id", "")
                })
        
        return chunks
    
    async def _check_originality(
        self,
        report_content: str,
        source_chunks: List[Dict[str, str]]
    ) -> OriginalityResult:
        """
        Perform originality checking.
        
        Args:
            report_content: The draft report content
            source_chunks: Source chunks to compare against
            
        Returns:
            OriginalityResult
        """
        # Split report into sentences/paragraphs
        sentences = self._split_into_sentences(report_content)
        
        flagged_passages = []
        acceptable_similarities = []
        
        # Check each sentence against sources
        for idx, sentence in enumerate(sentences):
            passage_id = f"sentence_{idx}"
            
            # Skip very short sentences
            if len(sentence.split()) < 5:
                continue
            
            # Check for similarity
            best_match = await self._find_best_match(sentence, source_chunks)
            
            if best_match:
                similarity_score = best_match["similarity_score"]
                
                # Determine if this is an exception (acceptable similarity)
                is_exception, exception_type = self._check_exceptions(sentence, best_match)
                
                if is_exception:
                    acceptable_similarities.append(AcceptableSimilarity(
                        passage_id=passage_id,
                        text=sentence,
                        similarity_score=similarity_score,
                        reason_for_acceptance=f"Exception: {exception_type}",
                        exception_type=exception_type
                    ))
                elif similarity_score >= self.MEDIUM_RISK_THRESHOLD:
                    # Flag as potential plagiarism
                    risk_level = "HIGH" if similarity_score >= self.HIGH_RISK_THRESHOLD else "MEDIUM"
                    
                    flagged_passages.append(FlaggedPassage(
                        passage_id=passage_id,
                        text=sentence,
                        matched_source={
                            "source_id": best_match["source_id"],
                            "source_text": best_match["source_text"],
                            "source_name": best_match["source"],
                            "tier": best_match.get("tier", "unknown")
                        },
                        similarity_score=similarity_score,
                        similarity_type="semantic",
                        risk_level=risk_level,
                        reason=f"Very similar phrasing to source (similarity: {similarity_score:.2f})",
                        rewrite_required=True,
                        suggested_action=self._generate_rewrite_suggestion(sentence)
                    ))
        
        # Calculate statistics
        statistics = OriginalityStatistics(
            total_sentences_checked=len(sentences),
            high_risk_flagged=len([f for f in flagged_passages if f.risk_level == "HIGH"]),
            medium_risk_flagged=len([f for f in flagged_passages if f.risk_level == "MEDIUM"]),
            low_risk_flagged=0,
            acceptable_matches=len(acceptable_similarities),
            pass_threshold=False
        )
        
        # Calculate overall originality score
        if len(sentences) == 0:
            overall_score = 1.0
        else:
            # Score based on flagged ratio
            flagged_ratio = len(flagged_passages) / len(sentences)
            overall_score = 1.0 - (flagged_ratio * 0.5)  # Reduce score by flagged percentage
        
        statistics.pass_threshold = (
            overall_score >= self.PASS_THRESHOLD and
            statistics.high_risk_flagged == 0 and
            statistics.medium_risk_flagged <= len(sentences) * 0.1
        )
        
        # Determine recommendation
        if statistics.pass_threshold:
            recommendation = "APPROVED"
            revision_notes = "Report passes originality check. Content is sufficiently original."
        else:
            recommendation = "REVISION_REQUIRED"
            revision_notes = f"{statistics.high_risk_flagged} HIGH risk and {statistics.medium_risk_flagged} MEDIUM risk passages require rewriting."
        
        # Specific rewrites needed
        specific_rewrites = [
            f"Passage {f.passage_id}: {f.text[:50]}..."
            for f in flagged_passages if f.risk_level == "HIGH"
        ]
        
        return OriginalityResult(
            overall_originality_score=overall_score,
            flagged_passages=flagged_passages,
            acceptable_similarities=acceptable_similarities,
            statistics=statistics,
            recommendation=recommendation,
            revision_notes=revision_notes,
            specific_rewrites_needed=specific_rewrites
        )
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        import re
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences
    
    async def _find_best_match(
        self,
        sentence: str,
        source_chunks: List[Dict[str, str]]
    ) -> Optional[Dict[str, Any]]:
        """
        Find best matching source chunk for a sentence.
        
        Args:
            sentence: Sentence to check
            source_chunks: List of source chunks
            
        Returns:
            Dict with match info or None
        """
        best_match = None
        best_score = 0.0
        
        # Try semantic similarity if embedding service available
        if self.embedding_service:
            try:
                sentence_emb = self.embedding_service.encode([sentence])
                if sentence_emb is None or len(sentence_emb) == 0:
                    raise ValueError("Failed to encode sentence")
                
                sentence_emb = sentence_emb[0]  # Get first (and only) embedding
                
                for chunk in source_chunks:
                    chunk_text = chunk["content"]
                    chunk_emb = self.embedding_service.encode([chunk_text])
                    
                    if chunk_emb is None or len(chunk_emb) == 0:
                        continue
                        
                    chunk_emb = chunk_emb[0]  # Get first (and only) embedding
                    
                    # Compute cosine similarity using numpy
                    import numpy as np
                    a, b = np.array(sentence_emb), np.array(chunk_emb)
                    norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
                    if norm_a == 0 or norm_b == 0:
                        similarity = 0.0
                    else:
                        similarity = float(np.dot(a, b) / (norm_a * norm_b))
                    
                    if similarity > best_score:
                        best_score = similarity
                        best_match = {
                            "source_text": chunk_text,
                            "source": chunk["source"],
                            "source_id": chunk.get("source_id", ""),
                            "source_type": chunk.get("source_type", ""),
                            "similarity_score": similarity
                        }
            except Exception as exc:
                logger.warning(f"Semantic similarity check failed: {exc}")
        
        # Fallback: simple n-gram matching
        if not best_match or best_score < 0.5:
            for chunk in source_chunks:
                chunk_text = chunk["content"]
                n_gram_score = self._n_gram_similarity(sentence, chunk_text)
                
                if n_gram_score > best_score:
                    best_score = n_gram_score
                    best_match = {
                        "source_text": chunk_text,
                        "source": chunk["source"],
                        "source_id": chunk.get("source_id", ""),
                        "source_type": chunk.get("source_type", ""),
                        "similarity_score": n_gram_score
                    }
        
        return best_match if best_score > 0.5 else None
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        import math
        
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def _n_gram_similarity(self, text1: str, text2: str, n: int = 8) -> float:
        """Compute n-gram similarity between two texts."""
        words1 = text1.lower().split()
        words2 = text2.lower().split()
        
        if len(words1) < n or len(words2) < n:
            return 0.0
        
        # Generate n-grams
        ngrams1 = set([" ".join(words1[i:i+n]) for i in range(len(words1) - n + 1)])
        ngrams2 = set([" ".join(words2[i:i+n]) for i in range(len(words2) - n + 1)])
        
        if not ngrams1 or not ngrams2:
            return 0.0
        
        # Calculate overlap
        overlap = len(ngrams1 & ngrams2)
        total = len(ngrams1 | ngrams2)
        
        return overlap / total if total > 0 else 0.0
    
    def _check_exceptions(self, sentence: str, match: Dict[str, Any]) -> tuple[bool, str]:
        """
        Check if similarity is an acceptable exception.
        
        Returns:
            (is_exception, exception_type)
        """
        sentence_lower = sentence.lower()
        
        # Check for numerical data
        import re
        if re.search(r'\d+', sentence):
            number_density = len(re.findall(r'\d+', sentence)) / len(sentence.split())
            if number_density > 0.3:
                return True, "numerical_data"
        
        # Check for standard definitions
        definition_keywords = ["is defined as", "refers to", "means", "is a measure of"]
        if any(kw in sentence_lower for kw in definition_keywords):
            return True, "standard_definition"
        
        # Check for proper quotes (has quotation marks)
        if '"' in sentence or "'" in sentence:
            return True, "quoted_text"
        
        # Check for short common phrases
        if len(sentence.split()) < 5:
            return True, "common_phrase"
        
        return False, ""
    
    def _generate_rewrite_suggestion(self, sentence: str) -> str:
        """Generate a suggestion for rewriting a flagged passage."""
        return (
            "Paraphrase this passage using different sentence structure and synonyms "
            "while maintaining the factual accuracy and proper citation."
        )


# Standalone function for graph integration
async def run_originality_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standalone function to run originality agent in LangGraph workflow.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state dict with originality check
    """
    from app.services.llm import get_llm_client
    from app.services.embeddings import get_embedding_service
    
    llm_client = get_llm_client()
    embedding_service = get_embedding_service()
    
    agent = OriginalityAgent(
        llm_client=llm_client,
        embedding_service=embedding_service
    )
    
    result = await agent.run(state)
    
    return {**state, **result}
