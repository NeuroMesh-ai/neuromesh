"""
🚀 TIMEOUT DYNAMIQUE - Suggestion d'amélioration pour BugBrain

Problème identifié par Denis Houet:
- Les timeouts fixes de 60s sont trop courts pour les gros modèles
- qwen3:8b peut prendre 10-30s
- LLaMA 3 70B peut prendre 60-120s
- Mixtral 8x7B peut prendre 20-60s

Solution proposée:
- Timeouts dynamiques basés sur la taille du modèle
- Configurable par l'utilisateur
- Valeurs par défaut intelligentes

"""

# ============================================================================
# ============== TIMEOUTS DYNAMIQUES ========================================
# ============================================================================

MODEL_TIMEOUTS = {
    # Petits modèles (< 4B params)
    "SmolLM2:1.7b": 60,
    "tinyllama:latest": 60,
    "Stable-code:3b": 60,
    "phi3:mini": 60,

    # Modèles moyens (4-10B params)
    "qwen3:8b": 180,        # 3 minutes
    "llama3:8b": 180,       # 3 minutes
    "mistral:7b": 180,      # 3 minutes
    "gemma:7b": 180,        # 3 minutes

    # Gros modèles (10-30B params)
    "qwen2:14b": 300,       # 5 minutes
    "llama2:13b": 300,      # 5 minutes
    "mistral-medium": 300,  # 5 minutes

    # Très gros modèles (30B+ params)
    "llama3:70b": 600,      # 10 minutes
    "mixtral:8x7b": 600,    # 10 minutes (47B total)
    "falcon:180b": 900,     # 15 minutes

    # Valeur par défaut
    "default": 120          # 2 minutes
}

def get_timeout_for_model(model: str) -> int:
    """
    Retourne le timeout approprié pour un modèle donné
    """
    return MODEL_TIMEOUTS.get(model, MODEL_TIMEOUTS["default"])

def estimate_response_time(model: str, prompt_length: int) -> int:
    """
    Estime le temps de réponse basé sur le modèle et la longueur du prompt
    """
    base_timeout = get_timeout_for_model(model)

    # Ajustement selon la longueur du prompt
    if prompt_length > 1000:
        # Prompts longs → plus de temps
        factor = 1.5
    elif prompt_length > 500:
        factor = 1.2
    else:
        factor = 1.0

    return int(base_timeout * factor)


# ============================================================================
# ============== CODE À INTÉGRER DANS BUGBRAIN ============================
# ============================================================================

"""
Dans bugbrain_v3_final.py, remplacer la fonction _query_ollama:

    async def _query_ollama(self, model: str, prompt: str, max_length: int = 500) -> Tuple[str, float]:
        \"\"\"Query Ollama via stdin avec timeout dynamique\"\"\"
        try:
            # Timeout dynamique basé sur le modèle
            timeout = get_timeout_for_model(model)

            # Ajustement selon la longueur du prompt
            if len(prompt) > 1000:
                timeout = int(timeout * 1.5)
            elif len(prompt) > 500:
                timeout = int(timeout * 1.2)

            start = time.time()
            result = subprocess.run(
                ["ollama", "run", model],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            latency = (time.time() - start) * 1000

            # Nettoyer les séquences ANSI
            cleaned = re.sub(r'\x1b\[[0-9;]*[mGKH]', '', result.stdout)

            return cleaned[:max_length], latency
        except subprocess.TimeoutExpired:
            return f"Error: Timeout after {timeout}s", float('inf')
        except Exception as e:
            return f"Error: {str(e)}", float('inf')
"""


# ============================================================================
# ============== CONFIGURATION UTILISATEUR =================================
# ============================================================================

class TimeoutConfig:
    """Configuration des timeouts"""
    def __init__(self):
        self.override_timeouts = {}  # Surcharge des timeouts par modèle
        self.default_timeout = 120   # Timeout par défaut global
        self.enable_dynamic = True   # Activer les timeouts dynamiques

    def get_timeout(self, model: str, prompt_length: int = 0) -> int:
        """
        Retourne le timeout final
        1. Override utilisateur si existe
        2. Timeout dynamique si activé
        3. Timeout par défaut
        """
        # 1. Override utilisateur
        if model in self.override_timeouts:
            return self.override_timeouts[model]

        # 2. Timeout dynamique
        if self.enable_dynamic:
            timeout = get_timeout_for_model(model)

            # Ajustement selon la longueur du prompt
            if prompt_length > 1000:
                timeout = int(timeout * 1.5)
            elif prompt_length > 500:
                timeout = int(timeout * 1.2)

            return timeout

        # 3. Timeout par défaut
        return self.default_timeout

    def set_timeout_override(self, model: str, timeout: int):
        """
        Définit un timeout override pour un modèle spécifique
        """
        self.override_timeouts[model] = timeout

    def set_default_timeout(self, timeout: int):
        """
        Définit le timeout par défaut global
        """
        self.default_timeout = timeout


# ============================================================================
# ============== EXEMPLES D'UTILISATION =====================================
# ============================================================================

if __name__ == "__main__":
    config = TimeoutConfig()

    print("📊 Timeouts dynamiques par modèle:")
    print()

    models = [
        "SmolLM2:1.7b",
        "phi3:mini",
        "qwen3:8b",
        "llama3:8b",
        "llama3:70b",
        "mixtral:8x7b"
    ]

    for model in models:
        timeout_short = config.get_timeout(model, prompt_length=100)
        timeout_medium = config.get_timeout(model, prompt_length=750)
        timeout_long = config.get_timeout(model, prompt_length=1500)

        print(f"{model:20s}")
        print(f"  Prompt court (<500):    {timeout_short}s")
        print(f"  Prompt moyen (500-1000): {timeout_medium}s")
        print(f"  Prompt long (>1000):    {timeout_long}s")
        print()

    print("🎯 Exemple d'override:")
    config.set_timeout_override("qwen3:8b", 300)  # Force 5 minutes
    print(f"qwen3:8b (override): {config.get_timeout('qwen3:8b')}s")