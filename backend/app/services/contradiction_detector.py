from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class ContradictionDetector:
    @staticmethod
    def detect(main_text_vec, evidence_vecs, threshold=0.35):
        contradictions = []
        for idx, ev in enumerate(evidence_vecs):
            sim = cosine_similarity([main_text_vec], [ev])[0][0]
            if sim < threshold:
                contradictions.append((idx, float(sim)))
        return contradictions
