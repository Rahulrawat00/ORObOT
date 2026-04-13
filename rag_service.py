import json
import math
import os
import re
import hashlib
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from email import policy
from email.parser import BytesParser
from html import unescape
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests


SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".py", ".json", ".csv", ".html", ".htm", ".eml", ".docx"
}
SYSTEM_SCAN_EXTENSIONS = {
    ".txt", ".md", ".docx", ".csv", ".html", ".htm"
}
SYSTEM_SKIP_DIR_NAMES = {
    ".git", "__pycache__", "venv", ".venv",
    "node_modules", "whatsapp_profile", "email_profile"
}
SYSTEM_SKIP_FILE_NAMES = {
    "main.py", "contacts.json", "rag_index.json"
}


@dataclass
class RAGResult:
    answer: str
    sources: List[Dict[str, str]]
    used_rag: bool


class PersonalRAG:
    def __init__(
        self,
        knowledge_dir: str = "knowledge",
        index_file: str = "rag_index.json",
        embed_model: str = "nomic-embed-text",
        llm_model: str = "llama3",
    ):
        self.knowledge_dir = Path(knowledge_dir)
        self.index_file = Path(index_file)
        self.embed_model = embed_model
        self.llm_model = llm_model
        self.http = requests.Session()
        self.index = self._load_index()
        self.system_roots = self._default_system_roots()

    def _default_system_roots(self) -> List[Path]:
        roots = []
        home = Path.home()
        candidates = [
            Path.cwd(),
            home / "Desktop",
            home / "Documents",
            home / "Downloads",
        ]
        seen = set()
        for p in candidates:
            key = str(p.resolve()) if p.exists() else str(p)
            if key in seen:
                continue
            seen.add(key)
            if p.exists() and p.is_dir():
                roots.append(p)
        return roots

    def _load_index(self) -> Dict:
        if not self.index_file.exists():
            return {"chunks": [], "created_at": None, "updated_at": None}
        try:
            with self.index_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"chunks": [], "created_at": None, "updated_at": None}
            data.setdefault("chunks", [])
            data.setdefault("created_at", None)

            data.setdefault("updated_at", None)
            return data
        except Exception:
            return {"chunks": [], "created_at": None, "updated_at": None}

    def _save_index(self):
        now = datetime.utcnow().isoformat()
        if not self.index.get("created_at"):
            self.index["created_at"] = now
        self.index["updated_at"] = now
        with self.index_file.open("w", encoding="utf-8") as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)

    def _deterministic_fallback_embedding(self, text: str, dims: int = 256) -> List[float]:
        vec = [0.0] * dims
        tokens = re.findall(r"[a-zA-Z0-9_]{2,}", (text or "").lower())
        if not tokens:
            return vec
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "little") % dims
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[bucket] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def _embed_text(self, text: str) -> List[float]:
        payload = {"model": self.embed_model, "prompt": text}
        try:
            res = self.http.post(
                "http://localhost:11434/api/embeddings",
                json=payload,
                timeout=(5, 60),
            )
            if res.ok:
                data = res.json()
                emb = data.get("embedding")
                if isinstance(emb, list) and emb:
                    return emb
        except Exception:
            pass
        return self._deterministic_fallback_embedding(text)

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        if not a or not b:
            return 0.0
        n = min(len(a), len(b))
        dot = sum(a[i] * b[i] for i in range(n))
        na = math.sqrt(sum(a[i] * a[i] for i in range(n)))
        nb = math.sqrt(sum(b[i] * b[i] for i in range(n)))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def _chunk_text(self, text: str, chunk_size: int = 850, overlap: int = 120) -> List[str]:
        clean = re.sub(r"\s+", " ", (text or "")).strip()
        if not clean:
            return []
        chunks = []
        start = 0
        while start < len(clean):
            end = min(start + chunk_size, len(clean))
            chunk = clean[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(clean):
                break
            start = max(0, end - overlap)
        return chunks

    def _read_text_file(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    def _read_eml_file(self, path: Path) -> Tuple[str, Dict[str, str]]:
        try:
            with path.open("rb") as f:
                msg = BytesParser(policy=policy.default).parse(f)
            sender = str(msg.get("From", "")).strip()
            subject = str(msg.get("Subject", "")).strip()
            date_header = str(msg.get("Date", "")).strip()
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype == "text/plain":
                        body += part.get_content().strip() + "\n"
            else:
                body = msg.get_content().strip()
            merged = f"From: {sender}\nSubject: {subject}\nDate: {date_header}\n\n{body}"
            return merged, {
                "email_from": sender,
                "email_subject": subject,
                "email_date_raw": date_header,
            }
        except Exception:
            return "", {}

    def _read_docx_file(self, path: Path) -> str:
        try:
            with zipfile.ZipFile(path, "r") as zf:
                xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
            texts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, flags=re.DOTALL)
            merged = " ".join(unescape(t) for t in texts)
            return re.sub(r"\s+", " ", merged).strip()
        except Exception:
            return ""

    def _parse_date_from_filename_or_meta(self, path: Path, extra_meta: Optional[Dict[str, str]] = None) -> Optional[str]:
        extra_meta = extra_meta or {}
        raw = extra_meta.get("email_date_raw", "")
        if raw:
            try:
                from email.utils import parsedate_to_datetime

                dt = parsedate_to_datetime(raw)
                if dt:
                    return dt.date().isoformat()
            except Exception:
                pass

        m = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
        if m:
            return m.group(1)
        return None

    def build_index(self) -> Dict[str, int]:
        if not self.knowledge_dir.exists():
            self.knowledge_dir.mkdir(parents=True, exist_ok=True)

        chunks = []
        files = [p for p in self.knowledge_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
        for file_path in files:
            ext = file_path.suffix.lower()
            extra_meta = {}
            if ext == ".eml":
                text, extra_meta = self._read_eml_file(file_path)
                source_type = "email"
            elif ext == ".docx":
                text = self._read_docx_file(file_path)
                source_type = "document"
            else:
                text = self._read_text_file(file_path)
                source_type = "document"

            if not text.strip():
                continue

            chunk_list = self._chunk_text(text)
            file_date = self._parse_date_from_filename_or_meta(file_path, extra_meta)
            for idx, chunk in enumerate(chunk_list):
                embedding = self._embed_text(chunk)
                chunks.append(
                    {
                        "id": f"{file_path.as_posix()}::{idx}",
                        "source": file_path.as_posix(),
                        "source_type": source_type,
                        "chunk_index": idx,
                        "text": chunk,
                        "embedding": embedding,
                        "source_date": file_date,
                        "meta": extra_meta,
                    }
                )

        self.index["chunks"] = chunks
        self._save_index()
        return {"files": len(files), "chunks": len(chunks)}

    def has_index(self) -> bool:
        return len(self.index.get("chunks", [])) > 0

    def _query_date_window(self, query: str) -> Optional[Tuple[str, str]]:
        q = (query or "").lower()
        today = datetime.utcnow().date()
        if "last week" in q:
            start = today - timedelta(days=7)
            return start.isoformat(), today.isoformat()
        if "last month" in q:
            start = today - timedelta(days=30)
            return start.isoformat(), today.isoformat()
        if "yesterday" in q:
            day = today - timedelta(days=1)
            return day.isoformat(), day.isoformat()
        if "today" in q:
            return today.isoformat(), today.isoformat()
        return None

    def _query_keywords(self, query: str) -> List[str]:
        tokens = re.findall(r"[a-zA-Z0-9_]{3,}", (query or "").lower())
        stop = {
            "what", "when", "where", "which", "who", "whom", "from", "with", "that",
            "this", "have", "your", "their", "about", "there", "would", "could",
            "should", "client", "last", "week", "month", "today", "yesterday",
            "please", "tell", "show", "find", "search", "asked", "ask"
        }
        return [t for t in tokens if t not in stop]

    def _quick_snippet(self, text: str, keywords: List[str], max_len: int = 420) -> str:
        txt = re.sub(r"\s+", " ", text or "").strip()
        if not txt:
            return ""
        if not keywords:
            return txt[:max_len]
        lower = txt.lower()
        pos = min((lower.find(k) for k in keywords if lower.find(k) >= 0), default=-1)
        if pos < 0:
            return txt[:max_len]
        start = max(0, pos - 120)
        end = min(len(txt), start + max_len)
        return txt[start:end]

    def _is_skipped_system_path(self, path: Path) -> bool:
        if path.name.lower() in SYSTEM_SKIP_FILE_NAMES:
            return True
        for part in path.parts:
            if part.lower() in SYSTEM_SKIP_DIR_NAMES:
                return True
        return False

    def _system_file_matches(
        self,
        query: str,
        top_k: int = 5,
        max_files_scan: int = 2000,
        max_file_size: int = 1_000_000,
        min_system_score: float = 0.35,
    ) -> List[Dict]:
        keywords = self._query_keywords(query)
        if not keywords:
            return []

        matched = []
        scanned = 0
        allowed = SYSTEM_SCAN_EXTENSIONS
        query_norm = (query or "").lower().strip()

        for root in self.system_roots:
            for path in root.rglob("*"):
                if scanned >= max_files_scan:
                    break
                if not path.is_file():
                    continue
                if self._is_skipped_system_path(path):
                    continue
                if path.suffix.lower() not in allowed:
                    continue
                scanned += 1
                try:
                    if path.stat().st_size > max_file_size:
                        continue
                    if path.suffix.lower() == ".docx":
                        text = self._read_docx_file(path)
                    else:
                        text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                low = text.lower()
                keyword_hits = 0
                for kw in keywords:
                    if kw in low:
                        keyword_hits += 1
                if keyword_hits <= 0:
                    continue
                coverage = keyword_hits / max(len(keywords), 1)
                phrase_bonus = 0.25 if query_norm and query_norm in low else 0.0
                filename_bonus = 0.15 if any(k in path.name.lower() for k in keywords) else 0.0
                doc_bonus = 0.05 if path.suffix.lower() in {".txt", ".md", ".docx"} else 0.0
                score = min(1.0, coverage + phrase_bonus + filename_bonus + doc_bonus)
                if score < min_system_score:
                    continue

                snippet = self._quick_snippet(text, keywords)
                matched.append(
                    {
                        "score": score,
                        "id": f"{path.as_posix()}::system",
                        "source": path.as_posix(),
                        "source_type": "system",
                        "chunk_index": 0,
                        "text": snippet,
                        "embedding": [],
                        "source_date": None,
                        "meta": {"scan_root": root.as_posix()},
                    }
                )
            if scanned >= max_files_scan:
                break

        matched.sort(key=lambda x: x.get("score", 0), reverse=True)
        deduped = []
        seen_sources = set()
        for item in matched:
            src = item.get("source")
            if not src or src in seen_sources:
                continue
            seen_sources.add(src)
            deduped.append(item)
            if len(deduped) >= top_k:
                break
        return deduped

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        if not self.has_index():
            return []
        query_embedding = self._embed_text(query)
        date_window = self._query_date_window(query)
        scored = []
        for item in self.index.get("chunks", []):
            src_date = item.get("source_date")
            if date_window and src_date:
                if not (date_window[0] <= src_date <= date_window[1]):
                    continue
            score = self._cosine_similarity(query_embedding, item.get("embedding", []))
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"score": s, **i} for s, i in scored[:top_k]]

    def _format_context(self, matches: List[Dict]) -> str:
        lines = []
        for i, m in enumerate(matches, 1):
            snippet = (m.get("text", "") or "").strip()
            lines.append(
                f"[{i}] source={m.get('source')} date={m.get('source_date') or 'unknown'}\n{snippet}"
            )
        return "\n\n".join(lines)

    def _llm_answer(self, query: str, matches: List[Dict]) -> str:
        context = self._format_context(matches)
        prompt = (
            "You are a personal knowledge assistant.\n"
            "Answer ONLY from the provided context.\n"
            "If context is insufficient, say: I could not find enough evidence.\n"
            "Keep it concise.\n\n"
            f"Question: {query}\n\n"
            f"Context:\n{context}\n\n"
            "Return answer with short inline citations like [1], [2]."
        )
        try:
            res = self.http.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 180,
                    },
                },
                timeout=(5, 90),
            )
            if res.ok:
                data = res.json()
                return (data.get("response") or "").strip()
        except Exception:
            pass
        if not matches:
            return "I could not find enough evidence."
        return f"Best match: {matches[0].get('text', '')[:240]}..."

    def answer(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.12,
        allow_system_fallback: bool = True,
    ) -> RAGResult:
        matches = self.retrieve(query, top_k=top_k)
        confident = [m for m in matches if m.get("score", 0) >= min_score]
        if allow_system_fallback:
            system_matches = self._system_file_matches(query, top_k=top_k)
            combined = confident + system_matches
            combined.sort(key=lambda m: m.get("score", 0), reverse=True)
            confident = combined[:top_k]
        if not confident:
            return RAGResult(
                answer="I could not find enough evidence in indexed knowledge or scanned system files.",
                sources=[],
                used_rag=False,
            )

        answer = self._llm_answer(query, confident)
        sources = []
        for i, m in enumerate(confident, 1):
            meta = m.get("meta", {}) or {}
            label = m.get("source")
            if m.get("source_type") == "email":
                subject = meta.get("email_subject", "").strip()
                sender = meta.get("email_from", "").strip()
                subject_part = f"{subject}" if subject else "No subject"
                sender_part = f" from {sender}" if sender else ""
                label = f"Email: {subject_part}{sender_part}"
            sources.append(
                {
                    "index": str(i),
                    "label": label or "Unknown source",
                    "path": m.get("source") or "",
                    "date": m.get("source_date") or "unknown",
                    "score": f"{m.get('score', 0):.3f}",
                }
            )
        return RAGResult(answer=answer, sources=sources, used_rag=True)
