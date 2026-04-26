# Auto-imports for extracted module
import logging
logger = logging.getLogger('UnityBrain.models')
from typing import List
from typing import Optional


class ModelRouter:
    """Routeur dynamique de modèles basé sur le contenu du prompt.
    
    Strategies de routing:
    - Code/dev → qwen3-coder (spécialiste)
    - Raisonnement/logique/math → deepseek (thinking model)
    - Chat/general → glm-5.1 (rapide, équilibré)
    - Si modèle demandé explicitement → utilise ce modèle
    - Si modèle indisponible → fallback intelligent
    """
    
    # Catégories de prompts avec mots-clés
    CATEGORIES = {
        'code': {
            'keywords': ['code', 'function', 'python', 'javascript', 'typescript', 'rust',
                         'program', 'script', 'debug', 'implement', 'class ', 'def ', 'async ',
                         'import ', 'return ', 'compile', 'refactor', 'api endpoint',
                         'fonction', 'programme', 'script', 'débog', 'implément', 'codez',
                         'écris un', 'write a', 'create a', 'build a'],
            'models': ['qwen3-coder-next:cloud', 'deepseek-v3.1:671b-cloud', 'glm-5.1:cloud'],
        },
        'reasoning': {
            'keywords': ['explique', 'analyse', 'raisonne', 'think', 'pourquoi', 'compare',
                         'why', 'how does', 'what if', 'calculate', 'solve', 'proof',
                         'logique', 'mathématique', 'déduire', 'infér', 'prouve',
                         'step by step', 'étape par étape', 'résonnement',
                         'démontr', 'what is the reason', 'caus'],
            'models': ['deepseek-v3.1:671b-cloud', 'glm-5.1:cloud', 'qwen3-coder-next:cloud'],
        },
        'creative': {
            'keywords': ['écris', 'write', 'story', 'histoire', 'poem', 'poème', 'creative',
                         'imagine', 'invent', 'fiction', 'narratif', 'romain',
                         'conte', 'chanson', 'song', 'letter', 'lettre'],
            'models': ['glm-5.1:cloud', 'deepseek-v3.1:671b-cloud', 'qwen3-coder-next:cloud'],
        },
        'factual': {
            'keywords': ['quoi', 'what is', 'qui', 'où', 'quand', 'combien',
                         'définition', 'definition', 'capitale', 'capital',
                         'explique-moi', 'tell me about', 'describe', 'décris',
                         'résumé', 'summary', 'liste', 'list'],
            'models': ['glm-5.1:cloud', 'deepseek-v3.1:671b-cloud', 'qwen3-coder-next:cloud'],
        },
    }
    
    # Fallback chains per model
    FALLBACK_CHAINS = {
        'glm-5.1:cloud': ['deepseek-v3.1:671b-cloud', 'qwen3-coder-next:cloud'],
        'deepseek-v3.1:671b-cloud': ['glm-5.1:cloud', 'qwen3-coder-next:cloud'],
        'qwen3-coder-next:cloud': ['glm-5.1:cloud', 'deepseek-v3.1:671b-cloud'],
    }
    
    # Approximate model speeds (ms for simple prompt) — lower = faster
    MODEL_SPEED = {
        'glm-5.1:cloud': 4000,
        'deepseek-v3.1:671b-cloud': 5000,
        'qwen3-coder-next:cloud': 15000,
    }
    
    async def route(self, prompt: str, available_models: List[str]) -> str:
        """Route le prompt vers le meilleur modèle disponible."""
        if not available_models:
            return 'glm-5.1:cloud'
        
        prompt_lower = prompt.lower()
        
        # Detect category by keyword scoring
        best_category = None
        best_score = 0
        for cat_name, cat_data in self.CATEGORIES.items():
            score = sum(1 for kw in cat_data['keywords'] if kw in prompt_lower)
            if score > best_score:
                best_score = score
                best_category = cat_name
        
        # If we detected a category, pick best available model from it
        if best_category and best_score >= 1:
            preferred = self.CATEGORIES[best_category]['models']
            for model in preferred:
                if model in available_models:
                    return model
        
        # Default: fastest model (glm-5.1)
        sorted_by_speed = sorted(available_models, key=lambda m: self.MODEL_SPEED.get(m, 99999))
        return sorted_by_speed[0]
    
    def get_fallback(self, model: str, available_models: List[str]) -> Optional[str]:
        """Get the best fallback model if the requested one fails."""
        chain = self.FALLBACK_CHAINS.get(model, [])
        for fallback in chain:
            if fallback in available_models:
                return fallback
        # Last resort: any available model
        return available_models[0] if available_models else None


# ============================================================================
# ============== ENSEMBLE CONSENSUS =======================================
# ============================================================================
