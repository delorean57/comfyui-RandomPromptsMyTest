import os
import random
import time
import logging
from pathlib import Path
from typing import Optional, Tuple
import folder_paths
import re

logger = logging.getLogger(__name__)

class RandomPromptsMyTest:
    """
    Ultimate random prompts node with:
    - Correct nested choices handling
    - Weighted random choices (e.g. {5::sunny|2::cloudy|1::rainy})
    - Wildcards support (__animal__)
    - Balanced random distribution (optional)
    - Comment removal
    - Max 3 consecutive blank lines in output
    """

    def __init__(self):
        self._random = random.Random()
        self._last_seed = None
        self._choice_history = {}
        self._wildcards_cache = {}
        self._wildcards_path = self._get_wildcards_path()

    def _get_wildcards_path(self) -> Optional[Path]:
        """Get path to wildcards folder"""
        node_dir = Path(__file__).parent
        wildcards_path = node_dir / "wildcards"
        wildcards_path.mkdir(exist_ok=True)
        return wildcards_path

    def _load_wildcard_file(self, wildcard: str) -> list[str]:
        """Load wildcard file if exists"""
        if not self._wildcards_path:
            return []
            
        wildcard_file = (self._wildcards_path / f"{wildcard}.txt")
        if wildcard_file.exists():
            try:
                with open(wildcard_file, "r", encoding="utf-8") as f:
                    return [line.strip() for line in f.readlines() if line.strip()]
            except Exception as e:
                logger.warning(f"Failed to load wildcard file {wildcard}: {e}")
        return []

    def _process_wildcards(self, text: str) -> str:
        """Process __wildcard__ syntax"""
        while "__" in text:
            start = text.find("__")
            end = text.find("__", start + 2)
            if end == -1:
                break
                
            wildcard_name = text[start+2:end]
            
            if wildcard_name not in self._wildcards_cache:
                self._wildcards_cache[wildcard_name] = self._load_wildcard_file(wildcard_name)
                
            options = self._wildcards_cache[wildcard_name]
            if options:
                replacement = self._random.choice(options)
                text = text[:start] + replacement + text[end+2:]
            else:
                text = text[:start] + wildcard_name + text[end+2:]
                
        return text

    def _reset_history(self):
        """Reset choice history"""
        self._choice_history = {}

    def _get_weighted_choice(self, choices: list[str], choice_block_id: str) -> str:
        """
        Selecciona una opción con pesos definidos como:
        {5::sunny|2::cloudy|1::rainy}
        """
        parsed_choices = []
        weights = []

        for c in choices:
            # Detectar formato "peso::texto"
            match = re.match(r"^\s*(\d+(?:\.\d+)?)::(.*)$", c)
            if match:
                weight = float(match.group(1))
                text = match.group(2).strip()
            else:
                weight = 1.0
                text = c.strip()

            parsed_choices.append(text)
            weights.append(weight)

        # Elegir con probabilidad ponderada
        selected = self._random.choices(parsed_choices, weights=weights, k=1)[0]
        return selected

    def _process_choices(self, text: str) -> str:
        """Main processing function that handles both simple and nested choices,
        ignoring // line comments and /* block comments */."""
        
        # 1. Eliminar comentarios
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
        text = re.sub(r"//.*", "", text)

        result = []
        i = 0
        while i < len(text):
            if text[i] == "{":
                # Buscar cierre correspondiente
                brace_level = 1
                j = i + 1
                while j < len(text) and brace_level > 0:
                    if text[j] == "{":
                        brace_level += 1
                    elif text[j] == "}":
                        brace_level -= 1
                    j += 1

                if brace_level == 0:
                    choice_block = text[i:j]
                    inner_content = choice_block[1:-1]

                    # Dividir las opciones por '|', manejando anidamientos
                    choices = []
                    current_choice = []
                    nested_level = 0

                    for char in inner_content:
                        if char == "{":
                            nested_level += 1
                            current_choice.append(char)
                        elif char == "}":
                            nested_level -= 1
                            current_choice.append(char)
                        elif char == "|" and nested_level == 0:
                            choices.append("".join(current_choice).strip())
                            current_choice = []
                        else:
                            current_choice.append(char)

                    if current_choice:
                        choices.append("".join(current_choice).strip())

                    # Procesar recursivamente
                    processed_choices = []
                    for choice in choices:
                        if "{" in choice:
                            processed_choices.append(self._process_choices(choice))
                        else:
                            processed_choices.append(choice)

                    # Seleccionar con pesos
                    if processed_choices:
                        choice_id = f"block_{i}_{hash(choice_block)}"
                        selected = self._get_weighted_choice(processed_choices, choice_id)
                        result.append(selected)

                    i = j
                else:
                    result.append(text[i])
                    i += 1
            else:
                result.append(text[i])
                i += 1

        return "".join(result)

    def _limit_blank_lines(self, text: str, max_consecutive: int = 3) -> str:
        """Reduce múltiples líneas en blanco consecutivas al límite dado."""
        pattern = r"(\n\s*){" + str(max_consecutive + 1) + r",}"
        replacement = "\n" * max_consecutive
        return re.sub(pattern, replacement, text)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "multiline": True,
                    "default": "{5::sunny|2::cloudy|1::rainy}",
                    "dynamicPrompts": False,
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xfffffffffffffff,
                    "step": 1,
                    "display": "number"
                }),
                "autorefresh": (["enabled", "disabled"], {
                    "default": "disabled",
                    "display": "combo"
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "generate"
    CATEGORY = "MyTest"
    OUTPUT_NODE = True

    def generate(self, text: str, seed: int, autorefresh: str) -> Tuple[str]:
        """Main generation function"""
        if seed > 0:
            if seed != self._last_seed:
                self._random.seed(seed)
                self._last_seed = seed
                self._reset_history()
        else:
            self._random.seed(int(time.time() * 1000) % (2**32))

        try:
            # Procesar comodines primero
            text = self._process_wildcards(text)
            
            # Luego procesar elecciones
            result = self._process_choices(text)

            # Limitar líneas en blanco consecutivas
            result = self._limit_blank_lines(result, max_consecutive=3)
            
            return (result,)
        except Exception as e:
            logger.error(f"Prompt generation failed: {e}")
            return ("Error in prompt generation",)

NODE_CLASS_MAPPINGS = {
    "RandomPromptsMyTest": RandomPromptsMyTest
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RandomPromptsMyTest": "Random Prompts MyTest"
}
