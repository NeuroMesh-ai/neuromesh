#!/usr/bin/env python3
"""
🤖 AUTO-SUPPORT - BugBrain répond lui-même aux questions de support
Système d'auto-support intelligent intégré

Usage:
    from src.auto_support import AutoSupport

    support = AutoSupport()
    answer = await support.handle_question("Comment configurer Ollama ?")
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import re

from .bugbrain_v3_final import BugBrain


class KnowledgeBase:
    """Base de connaissances pour le support"""

    def __init__(self):
        self.documents = []
        self.load_documentation()

    def load_documentation(self):
        """Charge la documentation"""
        # Chemin vers la documentation
        doc_dir = Path(__file__).parent.parent / "docs"

        # Fichiers de documentation à charger
        doc_files = [
            "README.md",
            "GUIDE_INTERFACE.md",
            "GUIDE_NETWORK_DEPLOYMENT.md",
            "GUIDE_INTERNET_CAPABLE.md",
            "GUIDE_TRUE_P2P.md",
            "GUIDE_PRODUCTION_ENHANCEMENT.md",
            "GUIDE_TIMEOUTS.md",
            "CHANGELOG.md",
            "CONTRIBUTING.md"
        ]

        for doc_file in doc_files:
            doc_path = doc_dir / doc_file
            if doc_path.exists():
                with open(doc_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.documents.append({
                        "file": doc_file,
                        "content": content
                    })

    def search(self, query: str, max_results: int = 3) -> List[Dict]:
        """Recherche dans la base de connaissances"""
        query_lower = query.lower()
        results = []

        for doc in self.documents:
            score = 0

            # Recherche simple par mots-clés
            words = query_lower.split()
            for word in words:
                if word in doc["content"].lower():
                    score += 1

            # Bonus pour le titre de fichier
            if any(word in doc["file"].lower() for word in words):
                score += 2

            if score > 0:
                results.append({
                    "file": doc["file"],
                    "score": score,
                    "content": doc["content"][:500]  # Extrait
                })

        # Trier par score
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:max_results]


class AutoSupport:
    """Système d'auto-support intelligent"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.model = self.config.get("model", "SmolLM2:1.7b")
        self.max_retries = self.config.get("max_retries", 3)
        self.confidence_threshold = self.config.get("confidence_threshold", 0.7)

        self.kb = KnowledgeBase()
        self.bugbrain = None
        self.history = []

        self.support_log = Path("logs/auto_support.log")

    async def initialize(self):
        """Initialise le système d'auto-support"""
        if not self.enabled:
            return False

        try:
            # Initialiser BugBrain
            self.bugbrain = BugBrain()
            self.bugbrain.model = self.model
            await self.bugbrain.initialize()

            return True
        except Exception as e:
            print(f"⚠️ Erreur initialisation auto-support: {e}")
            return False

    async def handle_question(
        self,
        question: str,
        user_id: str = "anonymous",
        context: Dict = None
    ) -> Dict:
        """
        Gère une question de support

        Returns:
            {
                "success": bool,
                "answer": str,
                "confidence": float,
                "sources": List[str],
                "escalated": bool,
                "message": str
            }
        """
        if not self.enabled:
            return {
                "success": False,
                "answer": "L'auto-support est désactivé.",
                "confidence": 0.0,
                "sources": [],
                "escalated": True,
                "message": "Veuillez contacter un humain pour le support."
            }

        question = question.strip()

        # Analyser la question
        question_type = self._classify_question(question)

        # Rechercher dans la base de connaissances
        kb_results = self.kb.search(question)

        # Générer la réponse
        for attempt in range(self.max_retries):
            try:
                # Construire le prompt
                prompt = self._build_prompt(question, kb_results, question_type)

                # Obtenir la réponse de BugBrain
                result = await self.bugbrain.query(prompt)

                if result.get("status") == "success":
                    answer = result.get("response", "").strip()

                    # Évaluer la confiance
                    confidence = self._evaluate_confidence(answer, kb_results)

                    # Si confiance suffisante
                    if confidence >= self.confidence_threshold:
                        # Logger
                        self._log_interaction(
                            question, answer, confidence, kb_results, user_id
                        )

                        return {
                            "success": True,
                            "answer": answer,
                            "confidence": confidence,
                            "sources": [r["file"] for r in kb_results],
                            "escalated": False,
                            "message": "Réponse générée avec succès."
                        }

            except Exception as e:
                print(f"⚠️ Erreur tentative {attempt + 1}: {e}")
                await asyncio.sleep(1)

        # Si toutes les tentatives échouent
        return {
            "success": False,
            "answer": self._generate_fallback_answer(kb_results),
            "confidence": 0.0,
            "sources": [r["file"] for r in kb_results],
            "escalated": True,
            "message": "Impossible de répondre avec confiance. Escalade vers humain."
        }

    def _classify_question(self, question: str) -> str:
        """
        Classifie le type de question
        """
        question_lower = question.lower()

        if any(kw in question_lower for kw in ["comment", "comment", "how", "comment faire"]):
            return "howto"
        elif any(kw in question_lower for kw in ["quoi", "what", "qu'est-ce"]):
            return "what"
        elif any(kw in question_lower for kw in ["erreur", "error", "bug", "problème", "issue"]):
            return "troubleshooting"
        elif any(kw in question_lower for kw in ["config", "configuration", "setup", "install"]):
            return "configuration"
        else:
            return "general"

    def _build_prompt(
        self,
        question: str,
        kb_results: List[Dict],
        question_type: str
    ) -> str:
        """
        Construit le prompt pour BugBrain
        """
        # Contexte de la base de connaissances
        kb_context = ""
        if kb_results:
            kb_context = "\n\n".join([
                f"Documentation: {doc['file']}\n{doc['content'][:300]}"
                for doc in kb_results[:2]
            ])

        # Prompt de support
        prompt = f"""Tu es l'assistant de support pour UnityBrain & BugBrain.
Réponds à cette question de manière claire et précise.

Question: {question}

Type: {question_type}

Documentation pertinente:
{kb_context}

Réponds en français, de manière concise et utile."""

        return prompt

    def _evaluate_confidence(self, answer: str, kb_results: List[Dict]) -> float:
        """
        Évalue la confiance dans la réponse
        """
        if not answer:
            return 0.0

        score = 0.5  # Score de base

        # Bonus si la réponse a du contenu
        if len(answer) > 50:
            score += 0.2

        # Bonus si la réponse contient des termes pertinents
        if kb_results:
            top_keywords = ["config", "setup", "install", "bug", "error", "fix", "use"]
            for keyword in top_keywords:
                if keyword in answer.lower():
                    score += 0.05

        # Bonus si la réponse mentionne la documentation
        if any(doc["file"] in answer for doc in kb_results):
            score += 0.1

        # Maximum 1.0
        return min(score, 1.0)

    def _generate_fallback_answer(self, kb_results: List[Dict]) -> str:
        """
        Génère une réponse de secours
        """
        if kb_results:
            sources = [doc["file"] for doc in kb_results[:3]]
            return f"""Je ne peux pas répondre avec confiance à cette question.

Documentation pertinente à consulter:
{chr(10).join(f"- {src}" for src in sources)}

Veuillez consulter la documentation ou contacter le support humain."""
        else:
            return "Je ne trouve pas de documentation pertinente. Veuillez consulter le README ou contacter le support humain."

    def _log_interaction(
        self,
        question: str,
        answer: str,
        confidence: float,
        sources: List[Dict],
        user_id: str
    ):
        """
        Log l'interaction
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "question": question,
            "answer": answer,
            "confidence": confidence,
            "sources": [s["file"] for s in sources]
        }

        self.history.append(log_entry)

        # Écrire dans le fichier de log
        try:
            self.support_log.parent.mkdir(exist_ok=True)
            with open(self.support_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"⚠️ Erreur écriture log: {e}")

    def get_stats(self) -> Dict:
        """
        Retourne les statistiques
        """
        if not self.history:
            return {
                "total_questions": 0,
                "avg_confidence": 0.0,
                "escalation_rate": 0.0
            }

        total = len(self.history)
        avg_conf = sum(h["confidence"] for h in self.history) / total
        escalations = sum(1 for h in self.history if h["confidence"] < self.confidence_threshold)

        return {
            "total_questions": total,
            "avg_confidence": avg_conf,
            "escalation_rate": escalations / total,
            "success_rate": 1.0 - (escalations / total)
        }

    def export_logs(self) -> List[Dict]:
        """
        Exporte les logs
        """
        return self.history.copy()


# ============================================================================
# ============== INTERFACE CLI POUR LE SUPPORT ============================
# ============================================================================

async def interactive_support():
    """Interface interactive de support"""
    support = AutoSupport()

    print("=" * 70)
    print("🤖 AUTO-SUPPORT - BugBrain Assistant")
    print("=" * 70)
    print("Tapez 'exit' pour quitter")
    print()

    if not await support.initialize():
        print("❌ Impossible d'initialiser l'auto-support")
        return

    user_id = input("ID utilisateur (optionnel): ").strip() or "anonymous"

    while True:
        question = input("\n❓ Votre question: ").strip()

        if question.lower() in ['exit', 'quit', 'quitter']:
            break

        if not question:
            continue

        print("\n🔍 Recherche de réponse...")
        result = await support.handle_question(question, user_id)

        if result["success"]:
            print(f"\n✅ Réponse (confiance: {result['confidence']:.2f})")
            print("-" * 70)
            print(result["answer"])
            print("-" * 70)

            if result["sources"]:
                print(f"\n📚 Sources: {', '.join(result['sources'])}")
        else:
            print(f"\n❌ {result['message']}")
            print(result["answer"])

    print("\n📊 Statistiques de la session:")
    stats = support.get_stats()
    print(f"   Questions: {stats['total_questions']}")
    print(f"   Confiance moy: {stats['avg_confidence']:.2f}")
    print(f"   Taux de succès: {stats['success_rate']:.2%}")


if __name__ == '__main__':
    asyncio.run(interactive_support())