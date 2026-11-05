"""
Script para fazer pull de prompts do LangSmith Prompt Hub.

Este script:
1. Conecta ao LangSmith usando credenciais do .env
2. Faz pull do prompt semente do desafio
3. Salva localmente em prompts/bug_to_user_story_v1.yml

DICAS DE IMPLEMENTAÇÃO:

- O pull é feito pelo cliente do LangSmith:

      from langsmith import Client
      client = Client()
      prompt = client.pull_prompt(
          "leonanluppi/bug_to_user_story_v1",
          dangerously_pull_public_prompt=True,
      )

- O parâmetro `dangerously_pull_public_prompt=True` é obrigatório sempre que o
  identificador tem dono explícito ("owner/nome"). O LangSmith bloqueia esse pull
  por padrão porque um prompt do Hub é um objeto LangChain serializado, que pode
  vir de terceiros. Aqui o prompt é o do desafio, então o risco é conhecido.

- O retorno é um ChatPromptTemplate. Para extrair o conteúdo das mensagens,
  use a serialização nativa do LangChain (`prompt.messages`, e o atributo
  `.prompt.template` de cada mensagem).

- Use `save_yaml` de utils.py para gravar o resultado no arquivo .yml.
"""

import os
import sys
from pathlib import Path
import yaml
from dotenv import load_dotenv
from langsmith import Client
from langchain_core.prompts import (
    AIMessagePromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from utils import save_yaml, check_env_vars, print_section_header

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PROMPT = "leonanluppi/bug_to_user_story_v1"
LOCAL_NAME = "bug_to_user_story_v1"
OUTPUT_FILE = PROJECT_ROOT / "prompts" / f"{LOCAL_NAME}.yml"

# Tipo da mensagem no LangChain -> campo no YAML
ROLE_TO_FIELD = {
    SystemMessagePromptTemplate: "system_prompt",
    HumanMessagePromptTemplate: "user_prompt",
    AIMessagePromptTemplate: "assistant_prompt",
}


def _literal_multiline_str(dumper, value: str):
    """Grava textos com várias linhas como bloco literal (|), legível no YAML."""
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


# save_yaml (utils.py) usa yaml.dump com o Dumper padrão
yaml.add_representer(str, _literal_multiline_str)


def prompt_to_dict(prompt) -> dict:
    """
    Converte o ChatPromptTemplate puxado do Hub para o formato YAML do projeto.

    Cada mensagem do template (SystemMessagePromptTemplate,
    HumanMessagePromptTemplate, ...) vira um campo `<role>_prompt`, com o
    texto cru do template (`message.prompt.template`).
    """
    data = {}
    for message in prompt.messages:
        template = getattr(getattr(message, "prompt", None), "template", None)
        if template is None:
            # Ex.: MessagesPlaceholder não tem template de texto
            continue
        field = next(
            (f for cls, f in ROLE_TO_FIELD.items() if isinstance(message, cls)), None
        )
        if field is None:
            print(f"   ⚠️  Mensagem ignorada (tipo não suportado): {type(message).__name__}")
            continue
        data[field] = template

    metadata = getattr(prompt, "metadata", None) or {}
    data["description"] = metadata.get(
        "lc_hub_description", "Prompt para converter relatos de bugs em User Stories"
    )
    data["input_variables"] = sorted(prompt.input_variables)
    data["source"] = SOURCE_PROMPT
    if metadata.get("lc_hub_commit_hash"):
        data["commit_hash"] = metadata["lc_hub_commit_hash"]
    data["version"] = "v1"
    return data


def pull_prompts_from_langsmith() -> bool:
    """Faz pull do prompt semente e salva em prompts/bug_to_user_story_v1.yml."""
    client = Client()

    print(f"Puxando prompt: {SOURCE_PROMPT}")
    try:
        prompt = client.pull_prompt(SOURCE_PROMPT, dangerously_pull_public_prompt=True)
    except Exception as e:
        print(f"❌ Falha ao puxar '{SOURCE_PROMPT}': {e}")
        return False

    prompt_data = prompt_to_dict(prompt)
    if "system_prompt" not in prompt_data:
        print("❌ O prompt puxado não contém mensagem de system")
        return False

    if not save_yaml({LOCAL_NAME: prompt_data}, str(OUTPUT_FILE)):
        return False

    print(f"   ✓ Mensagens: {[k for k in prompt_data if k.endswith('_prompt')]}")
    print(f"   ✓ Variáveis: {prompt_data['input_variables']}")
    print(f"   ✓ Salvo em: {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")
    return True


def main():
    """Função principal"""
    print_section_header("PULL DE PROMPTS DO LANGSMITH HUB")

    if not check_env_vars(["LANGSMITH_API_KEY"]):
        return 1

    if not pull_prompts_from_langsmith():
        return 1

    print("\n✅ Pull concluído. Próximo passo: otimizar em prompts/bug_to_user_story_v2.yml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
