"""
Testes automatizados para validação de prompts.
"""
import re
import pytest
import yaml
import sys
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils import validate_prompt_structure

PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "bug_to_user_story_v2.yml"
PROMPT_KEY = "bug_to_user_story_v2"


def load_prompts(file_path: str):
    """Carrega prompts do arquivo YAML."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def prompt_data():
    data = load_prompts(PROMPT_FILE)
    assert PROMPT_KEY in data, f"Chave '{PROMPT_KEY}' não encontrada em {PROMPT_FILE.name}"
    return data[PROMPT_KEY]


@pytest.fixture(scope="module")
def system_prompt(prompt_data):
    return prompt_data.get("system_prompt") or ""


class TestPrompts:
    def test_prompt_has_system_prompt(self, prompt_data):
        """Verifica se o campo 'system_prompt' existe e não está vazio."""
        assert "system_prompt" in prompt_data
        assert isinstance(prompt_data["system_prompt"], str)
        assert prompt_data["system_prompt"].strip()

    def test_prompt_has_role_definition(self, system_prompt):
        """Verifica se o prompt define uma persona (ex: "Você é um Product Manager")."""
        persona = re.search(r"Você é (um|uma) ([^.\n]+)", system_prompt)
        assert persona, "system_prompt deve definir uma persona com 'Você é um/uma ...'"
        assert re.search(
            r"product (owner|manager)|analista|especialista",
            persona.group(2),
            re.IGNORECASE,
        ), f"Persona sem papel de produto/análise: {persona.group(0)!r}"

    def test_prompt_mentions_format(self, system_prompt):
        """Verifica se o prompt exige formato Markdown ou User Story padrão."""
        assert re.search(r"user story|markdown", system_prompt, re.IGNORECASE)
        # Estrutura padrão de User Story: Como um ..., eu quero ..., para que ...
        assert "Como um" in system_prompt
        assert "eu quero" in system_prompt
        assert "para que" in system_prompt
        # Critérios de aceitação em Gherkin
        for keyword in ("Critérios de Aceitação", "Dado que", "Quando", "Então"):
            assert keyword in system_prompt, f"Formato não menciona '{keyword}'"

    def test_prompt_has_few_shot_examples(self, system_prompt):
        """Verifica se o prompt contém exemplos de entrada/saída (técnica Few-shot)."""
        inputs = len(re.findall(r"^Relato:", system_prompt, re.MULTILINE))
        outputs = len(re.findall(r"^Resposta:", system_prompt, re.MULTILINE))
        assert inputs >= 2, f"Few-shot requer >= 2 exemplos de entrada, encontrados {inputs}"
        assert inputs == outputs, "Cada exemplo de entrada (Relato:) deve ter uma saída (Resposta:)"
        assert re.search(r"Exemplo", system_prompt)

    def test_prompt_no_todos(self, prompt_data):
        """Garante que você não esqueceu nenhum `[TODO]` no texto."""
        full_text = yaml.safe_dump(prompt_data, allow_unicode=True)
        assert "[TODO]" not in full_text
        assert not re.search(r"\bTODO\b", full_text)

    def test_minimum_techniques(self, prompt_data):
        """Verifica (através dos metadados do yaml) se pelo menos 2 técnicas foram listadas."""
        techniques = prompt_data.get("techniques_applied")
        assert isinstance(techniques, list)
        assert len(techniques) >= 2
        assert len(set(techniques)) == len(techniques), "Técnicas duplicadas"
        assert any("few_shot" in t for t in techniques), "Few-shot é obrigatório"

    # Testes extras: garantem que o prompt funciona na avaliação

    def test_structure_is_valid(self, prompt_data):
        """O prompt passa na validação usada pelo projeto (utils.validate_prompt_structure)."""
        is_valid, errors = validate_prompt_structure(prompt_data)
        assert is_valid, errors

    def test_bug_report_only_in_user_prompt(self, prompt_data, system_prompt):
        """{bug_report} deve estar só no user_prompt e ser a única variável do template."""
        from langchain_core.prompts import ChatPromptTemplate

        assert "{bug_report}" in prompt_data.get("user_prompt", "")
        assert "{bug_report}" not in system_prompt
        template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", prompt_data["user_prompt"]),
        ])
        assert set(template.input_variables) == {"bug_report"}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
