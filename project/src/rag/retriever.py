"""
Lung knowledge base retriever with support for multiple documentation sources.

Retrieves relevant clinical guidelines based on detection results.
"""

import os
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger("lung_nodule_retriever")


def retrieve_knowledge(query: str = "", num_results: int = 3, 
                      knowledge_base_dir: str = "src/rag/knowledge_base") -> str:
    """
    Retrieve relevant knowledge from the knowledge base.
    
    Args:
        query: Search query (if empty, returns general guidelines)
        num_results: Number of relevant passages to return
        knowledge_base_dir: Path to knowledge base directory
        
    Returns:
        Concatenated relevant passages from knowledge base
    """
    
    # List of knowledge base files in priority order
    kb_files = [
        "nccn_guidelines.txt",
        "medical_notes.txt", 
        "lung_nodule_rules.txt"
    ]
    
    results = []
    
    for kb_file in kb_files:
        kb_path = os.path.join(knowledge_base_dir, kb_file)
        
        if not os.path.exists(kb_path):
            logger.warning(f"Knowledge base file not found: {kb_path}")
            continue
        
        try:
            with open(kb_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not query:
                # Return all content if no query
                results.append(content)
            else:
                # Find relevant passages
                passages = _find_relevant_passages(content, query, max_passages=num_results)
                results.extend(passages)
                
        except Exception as e:
            logger.error(f"Error reading knowledge base {kb_path}: {e}")
            continue
    
    # Combine results
    knowledge = "\n\n---\n\n".join(results[:num_results])
    
    if not knowledge:
        logger.warning("No knowledge base content retrieved, using defaults")
        knowledge = _get_default_guidelines()
    
    return knowledge


def _find_relevant_passages(content: str, query: str, max_passages: int = 3) -> List[str]:
    """
    Find relevant passages from content based on query.
    Simple keyword-based retrieval.
    """
    # Split into passages (paragraphs)
    passages = content.split('\n\n')
    
    # Score each passage
    scored = []
    query_words = query.lower().split()
    
    for passage in passages:
        if not passage.strip():
            continue
        
        # Simple scoring: count keyword matches
        score = 0
        passage_lower = passage.lower()
        
        for word in query_words:
            if word in passage_lower:
                score += passage_lower.count(word)
        
        if score > 0:
            scored.append((passage, score))
    
    # Sort by score and return top passages
    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:max_passages]]


def _get_default_guidelines() -> str:
    """
    Return default clinical guidelines for lung nodule management.
    """
    return """
LUNG NODULE CLASSIFICATION AND MANAGEMENT GUIDELINES

1. NODULE SIZE RISK STRATIFICATION
   - 0-3 mm: Minimal risk - No follow-up needed in most cases
   - 3-4 mm: Low risk - Follow-up CT at 12 months
   - 4-6 mm: Intermediate risk - Follow-up at 3-6 months
   - 6-8 mm: Higher risk - Consider short-term follow-up or biopsy
   - >8 mm: High risk - Consider further workup, referral to pulmonology

2. NODULE CHARACTERISTICS
   - Solid vs. part-solid vs. ground-glass (GGN)
   - Location (peripheral, central, near hilum)
   - Morphology (smooth, irregular, spiculated)
   - Density pattern (homogeneous vs. heterogeneous)

3. FOLLOW-UP RECOMMENDATIONS
   - Low-risk stable nodule: Annual CT up to 5 years
   - Intermediate-risk nodule: CT at 3-6 months then annually
   - High-risk nodule: Urgent specialist consultation

4. CLINICAL RISK FACTORS
   - Age >50 years
   - Smoking history (pack-years)
   - Family history of lung cancer
   - Prior malignancy
   - COPD diagnosis

5. MANAGEMENT APPROACH
   - Nodules <4 mm: Generally no follow-up
   - Nodules 4-6 mm: Low-dose CT at 12 months (if not seen on prior CT)
   - Nodules 6-8 mm: Consider CT at 3-6 months and then annually
   - Nodules >8 mm: Workup including consider PET-CT or biopsy if solid

6. AI DETECTION INTERPRETATION
   - AI: High sensitivity detection (~95-98%)
   - Radiologist correlation essential for final diagnosis
   - This is a SCREENING TOOL, not diagnostic
   - Clinical context required for management decisions.
    """


def retrieve_nodule_guidelines(size_mm: float = None, nodule_count: int = 1) -> str:
    """
    Retrieve specific guidelines based on detection characteristics.
    
    Args:
        size_mm: Nodule size in millimeters
        nodule_count: Number of nodules detected
        
    Returns:
        Relevant guidelines for the detected nodules
    """
    
    query = ""
    
    if size_mm is not None:
        if size_mm < 3:
            query = "nodule 3mm risk stratification follow-up"
        elif size_mm < 4:
            query = "nodule 3-4mm follow-up management"
        elif size_mm < 6:
            query = "nodule 4-6mm intermediate risk"
        elif size_mm < 8:
            query = "nodule 6-8mm higher risk follow-up"
        else:
            query = "nodule >8mm high risk workup biopsy"
    
    if nodule_count > 1:
        query += " multiple nodules management"
    
    return retrieve_knowledge(query, num_results=5)

