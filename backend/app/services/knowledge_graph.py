# backend/app/services/knowledge_graph.py
"""
Upgraded knowledge graph extractor.
Uses spaCy NER for English (fallback heuristics for other languages),
builds co-occurrence edges, and computes node scores for frontend.
"""
import os
from typing import Dict, Any, List
try:
    import spacy
except Exception:
    spacy = None

try:
    import networkx as nx
    from networkx.readwrite import json_graph
except Exception:
    nx = None
    json_graph = None

# try to load english model, gracefully fallback
nlp = None
if spacy:
    try:
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        try:
            nlp = spacy.load("xx_ent_wiki_sm")
        except Exception:
            nlp = None

def extract_entities(text: str, max_entities: int = 60) -> List[Dict[str, str]]:
    if not text:
        return []
    # prefer spaCy if available
    if nlp:
        try:
            doc = nlp(text[:20000])
            ents = []
            seen_texts = set()
            for e in doc.ents:
                txt = e.text.strip()
                if txt and txt not in seen_texts:
                    ents.append({"text": txt, "label": e.label_})
                    seen_texts.add(txt)
                if len(ents) >= max_entities:
                    break
            return ents
        except Exception:
            pass
    # fallback: simple capitalized phrases heuristic
    tokens = text.split()
    ents = []
    for i in range(len(tokens) - 1):
        if tokens[i].istitle():
            cand = tokens[i]
            if tokens[i+1].istitle():
                cand = cand + " " + tokens[i+1]
            if cand not in [e["text"] for e in ents]:
                ents.append({"text": cand, "label": "PROB"})
        if len(ents) >= max_entities:
            break
    return ents

def build_graph(text: str) -> Dict[str, Any]:
    # nodes are unique entity strings; links are co-occurrence in sentences
    ents = extract_entities(text)
    nodes = []
    links = []
    if not ents:
        return {"nodes": [], "links": []}

    # create id mapping
    id_for = {}
    for i, e in enumerate(ents):
        nid = f"n{i}"
        id_for[e["text"]] = nid
        nodes.append({"id": nid, "label": e["text"], "group": e.get("label","ENT")})

    # build co-occurrence counts
    sent_sep = [s.strip() for s in text.split('.') if s.strip()]
    co = {}
    for s in sent_sep:
        found = [e["text"] for e in ents if e["text"] in s]
        for i in range(len(found)):
            for j in range(i+1, len(found)):
                a = id_for[found[i]]
                b = id_for[found[j]]
                key = tuple(sorted([a,b]))
                co[key] = co.get(key, 0) + 1
    for (a,b),w in co.items():
        links.append({"source": a, "target": b, "weight": w})

    # if networkx available, compute node centrality and attach as metadata
    if nx and nodes:
        G = nx.Graph()
        for n in nodes:
            G.add_node(n["id"])
        for l in links:
            G.add_edge(l["source"], l["target"], weight=l.get("weight",1))
        try:
            central = nx.degree_centrality(G)
            for n in nodes:
                n["score"] = round(float(central.get(n["id"],0)),3)
        except Exception:
            pass

    return {"nodes": nodes, "links": links}
