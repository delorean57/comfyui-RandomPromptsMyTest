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
    - Weighted random choices (e.g. {5::sunny|2::cloudy|1::rainy})
    - Nested choice support
    - Wildcards (__animal__)
    - Comment removal
    - Optional blank line limiter with toggle
    """

    def __init__(self):
        self._random = random.Random()
        self._last_seed = None
        self._choice_history = {}
        self._wildcards_cache = {}
        self._wildcards_path = self._get_wildcards_path()

    def _get_wildcards_path(self) -> Optional[Path]:
        node_dir = Path(__file__).parent
        wildcards_path = node_dir / "wildcards"
        wildcards_path.mkdir(exist_ok=True)
        return wildcards_path

    def _load_wildcard_file(self, wildcard: str) -> list[str]:
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
        self._choice_history = {}

    def _get_weighted_choice(self, choices: list[str], choice_block_id: str) -> str:
        parsed_choices = []
        weights = []
        for c in choices:
            match = re.match(r"^\s*(\d+(?:\.\d+)?)::(.*)$", c)
            if match:
                weight = float(match.group(1))
                text = match.group(2).strip()
            else:
                weight = 1.0
                text = c.strip()
            parsed_choices.append(text)
            weights.append(weight)
        return self._random.choices(parsed_choices, weights=weights, k=1)[0]

    def _process_choices(self, text: str) -> str:
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
        text = re.sub(r"//.*", "", text)
        result = []
        i = 0
        while i < len(text):
            if text[i] == "{":
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
                    inner = choice_block[1:-1]
                    choices = []
                    current = []
                    nested = 0
                    for ch in inner:
                        if ch == "{":
                            nested += 1
                            current.append(ch)
                        elif ch == "}":
                            nested -= 1
                            current.append(ch)
                        elif ch == "|" and nested == 0:
                            choices.append("".join(current).strip())
                            current = []
                        else:
                            current.append(ch)
                    if current:
                        choices.append("".join(current).strip())
                    processed = []
                    for c in choices:
                        processed.append(self._process_choices(c) if "{" in c else c)
                    if processed:
                        choice_id = f"block_{i}_{hash(choice_block)}"
                        selected = self._get_weighted_choice(processed, choice_id)
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
        pattern = r"(\n\s*){" + str(max_consecutive + 1) + r",}"
        return re.sub(pattern, "\n" * max_consecutive, text)

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
                "limit_blank_lines": (["enabled", "disabled"], {
                    "default": "enabled",
                    "display": "combo"
                }),
                "max_blank_lines": ("INT", {
                    "default": 3,
                    "min": 0,
                    "max": 10,
                    "step": 1,
                    "display": "number",
                    "enabled": lambda inputs: inputs.get("limit_blank_lines", "enabled") == "enabled"
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

    def generate(self, text: str, seed: int, limit_blank_lines: str, max_blank_lines: int, autorefresh: str) -> Tuple[str]:
        if seed > 0:
            if seed != self._last_seed:
                self._random.seed(seed)
                self._last_seed = seed
                self._reset_history()
        else:
            self._random.seed(int(time.time() * 1000) % (2**32))

        try:
            text = self._process_wildcards(text)
            result = self._process_choices(text)

            if limit_blank_lines == "enabled":
                result = self._limit_blank_lines(result, max_consecutive=max_blank_lines)

            return (result,)
        except Exception as e:
            logger.error(f"Prompt generation failed: {e}")
            return ("Error in prompt generation",)


NODE_CLASS_MAPPINGS = {"RandomPromptsMyTest": RandomPromptsMyTest}
NODE_DISPLAY_NAME_MAPPINGS = {"RandomPromptsMyTest": "Random Prompts MyTest"}
