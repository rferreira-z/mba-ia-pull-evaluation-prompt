"""
Script para fazer push de prompts otimizados ao LangSmith Prompt Hub.

Este script:
1. Lê os prompts otimizados de prompts/bug_to_user_story_v2.yml
2. Valida os prompts
3. Faz push PÚBLICO para o LangSmith Hub
4. Adiciona metadados (tags, descrição, técnicas utilizadas)

DICAS DE IMPLEMENTAÇÃO:

- O push é feito pelo cliente do LangSmith:

      from langsmith import Client
      from langchain_core.prompts import ChatPromptTemplate

      client = Client()
      prompt = ChatPromptTemplate.from_messages([
          ("system", system_prompt),
          ("user", user_prompt),
      ])
      url = client.push_prompt(
          f"{username}/bug_to_user_story_v2",
          object=prompt,
          is_public=True,
          description="...",
          tags=[...],
      )

- `username` vem de USERNAME_LANGSMITH_HUB no .env e precisa ser o seu handle
  do Hub. Se você ainda não tem um handle, veja as instruções no .env.example.

- A variável do template precisa ser {bug_report}, que é a chave de entrada
  usada no dataset de avaliação.

- Use `load_yaml` de utils.py para ler o arquivo .yml.
"""

import os
import sys
from dotenv import load_dotenv
from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate
from pathlib import Path
from utils import load_yaml, check_env_vars, print_section_header, validate_prompt_structure

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_KEY = "bug_to_user_story_v2"
PROMPT_FILE = PROJECT_ROOT / "prompts" / f"{PROMPT_KEY}.yml"
INPUT_VARIABLE = "bug_report"


def build_readme(prompt_name: str, prompt_data: dict) -> str:
    """Monta o README exibido na página do prompt no Hub."""
    techniques = "\n".join(f"- {t}" for t in prompt_data.get("techniques_applied", []))
    return (
        f"# {prompt_name}\n\n"
        f"{prompt_data.get('description', '')}\n\n"
        f"**Versão:** {prompt_data.get('version', '')}\n\n"
        f"## Técnicas aplicadas\n{techniques}\n\n"
        f"## Entrada\n- `{{{INPUT_VARIABLE}}}`: relato de bug em texto livre\n"
    )


def push_prompt_to_langsmith(prompt_name: str, prompt_data: dict) -> bool:
    """
    Faz push do prompt otimizado para o LangSmith Hub (PÚBLICO).

    Args:
        prompt_name: Nome do prompt
        prompt_data: Dados do prompt

    Returns:
        True se sucesso, False caso contrário
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_data["system_prompt"]),
        ("user", prompt_data["user_prompt"]),
    ])

    techniques = prompt_data.get("techniques_applied", [])
    tags = list(dict.fromkeys(
        list(prompt_data.get("tags", []))
        + [f"technique:{t}" for t in techniques]
        + [str(prompt_data.get("version", ""))]
    ))

    client = Client()
    try:
        url = client.push_prompt(
            prompt_name,
            object=prompt,
            is_public=True,
            description=prompt_data.get("description"),
            readme=build_readme(prompt_name, prompt_data),
            tags=[t for t in tags if t],
            commit_description=prompt_data.get("change_log") or None,
        )
    except Exception as e:
        # O Hub responde 409 quando o conteúdo é idêntico ao último commit
        if "Nothing to commit" in str(e) or "409" in str(e):
            print("   ℹ️  Sem alterações em relação ao último commit; nada a enviar.")
            return True
        print(f"❌ Falha no push de '{prompt_name}': {e}")
        return False

    print(f"   ✓ Push concluído (público): {url}")
    print(f"   ✓ Tags: {tags}")
    return True


def validate_prompt(prompt_data: dict) -> tuple[bool, list]:
    """
    Valida estrutura básica de um prompt (versão simplificada).

    Args:
        prompt_data: Dados do prompt

    Returns:
        (is_valid, errors) - Tupla com status e lista de erros
    """
    _, errors = validate_prompt_structure(prompt_data)

    user_prompt = (prompt_data.get("user_prompt") or "").strip()
    system_prompt = prompt_data.get("system_prompt") or ""
    placeholder = f"{{{INPUT_VARIABLE}}}"

    if not user_prompt:
        errors.append("user_prompt está vazio")
    elif placeholder not in user_prompt:
        errors.append(f"user_prompt deve conter a variável {placeholder}")

    if placeholder in system_prompt:
        errors.append(f"{placeholder} deve ficar só no user_prompt (evita duplicar o relato)")

    # Garante que o template só depende de {bug_report}: chaves soltas nos
    # exemplos few-shot virariam variáveis e quebrariam a avaliação.
    try:
        variables = set(ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt),
        ]).input_variables)
        if variables != {INPUT_VARIABLE}:
            errors.append(
                f"Variáveis do template devem ser só {{{INPUT_VARIABLE}}}, encontradas: "
                f"{sorted(variables)} (escape chaves literais como {{{{ }}}})"
            )
    except Exception as e:
        errors.append(f"Template inválido: {e}")

    return (len(errors) == 0, errors)


def main():
    """Função principal"""
    print_section_header("PUSH DE PROMPTS OTIMIZADOS")

    if not check_env_vars(["LANGSMITH_API_KEY", "USERNAME_LANGSMITH_HUB"]):
        return 1

    data = load_yaml(str(PROMPT_FILE))
    if not data or PROMPT_KEY not in data:
        print(f"❌ Chave '{PROMPT_KEY}' não encontrada em {PROMPT_FILE.relative_to(PROJECT_ROOT)}")
        return 1
    prompt_data = data[PROMPT_KEY]

    is_valid, errors = validate_prompt(prompt_data)
    if not is_valid:
        print("❌ Prompt inválido:")
        for error in errors:
            print(f"   - {error}")
        return 1
    print("✓ Prompt validado")

    prompt_name = f"{os.getenv('USERNAME_LANGSMITH_HUB')}/{PROMPT_KEY}"
    print(f"\nEnviando: {prompt_name}")
    if not push_prompt_to_langsmith(prompt_name, prompt_data):
        return 1

    print("\n✅ Push concluído. Próximo passo: python src/evaluate.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
