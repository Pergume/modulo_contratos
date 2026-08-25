"""
abrir_sigo.py
-------------
Iniciador do SIGO para uso diário.

Faz tudo o que antes era manual:
  1. confere se as bibliotecas necessárias estão instaladas (instala se faltar);
  2. escolhe uma porta livre (se a 8000 estiver ocupada, tenta as seguintes);
  3. sobe o servidor;
  4. espera a porta responder e só então abre o navegador — assim a página
     nunca aparece com erro de "não foi possível conectar";
  5. mantém a janela aberta mostrando o que está acontecendo.

Para encerrar, feche esta janela ou pressione Ctrl+C.

Este arquivo é o que o atalho da Área de Trabalho executa.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
BACKEND = RAIZ / "backend"
PORTA_INICIAL = 8000
TENTATIVAS_PORTA = 20

PACOTES = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("openpyxl", "openpyxl"),
    ("multipart", "python-multipart"),
]


def _titulo() -> None:
    print("=" * 62)
    print("  SIGO — Gestão de Contratos e Apoio à Decisão")
    print("  Secretaria Municipal de Economia — Porto Velho")
    print("=" * 62)


def _conferir_dependencias() -> bool:
    faltando = []
    for modulo, pacote in PACOTES:
        try:
            __import__(modulo)
        except ImportError:
            faltando.append(pacote)

    if not faltando:
        return True

    print(f"\nFaltam bibliotecas: {', '.join(faltando)}")
    print("Instalando (só é necessário na primeira vez)...\n")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", *faltando],
        cwd=str(RAIZ),
    )
    if r.returncode != 0:
        print("\nNão foi possível instalar automaticamente.")
        print("Abra o Prompt de Comando nesta pasta e execute:")
        print(f"    {Path(sys.executable).name} -m pip install -r requirements.txt")
        return False

    for modulo, pacote in PACOTES:
        try:
            __import__(modulo)
        except ImportError:
            print(f"\nA biblioteca '{pacote}' continua indisponível.")
            return False
    return True


def _porta_livre(inicial: int, tentativas: int) -> int | None:
    for porta in range(inicial, inicial + tentativas):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", porta))
                return porta
            except OSError:
                continue
    return None


def _esperar_porta(porta: int, limite_s: float = 90.0) -> bool:
    fim = time.time() + limite_s
    while time.time() < fim:
        try:
            with socket.create_connection(("127.0.0.1", porta), 0.5):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def _abrir_navegador(porta: int) -> None:
    if not _esperar_porta(porta):
        print("\nO servidor demorou mais que o esperado para responder.")
        print(f"Tente abrir manualmente: http://127.0.0.1:{porta}/")
        return
    url = f"http://127.0.0.1:{porta}/"
    print(f"\nPainel disponível em {url}")
    print("Abrindo o navegador...\n")
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        print(f"Abra manualmente: {url}")


def main() -> int:
    _titulo()

    if not BACKEND.is_dir():
        print(f"\nPasta 'backend' não encontrada em {RAIZ}.")
        print("Mantenha este arquivo dentro da pasta do sistema.")
        return 1

    if not _conferir_dependencias():
        return 1

    porta = _porta_livre(PORTA_INICIAL, TENTATIVAS_PORTA)
    if porta is None:
        print(f"\nNenhuma porta livre entre {PORTA_INICIAL} e "
              f"{PORTA_INICIAL + TENTATIVAS_PORTA - 1}.")
        return 1
    if porta != PORTA_INICIAL:
        print(f"\nA porta {PORTA_INICIAL} está ocupada "
              f"(o SIGO já pode estar aberto). Usando a {porta}.")

    pacotes = RAIZ / "pacotes"
    zips = sorted(pacotes.glob("*.zip")) if pacotes.is_dir() else []
    print(f"\nPasta de pacotes : {pacotes}")
    print(f"Pacotes disponíveis: {len(zips)}"
          + (f" (mais recente: {zips[-1].name})" if zips else ""))

    threading.Thread(target=_abrir_navegador, args=(porta,), daemon=True).start()

    print("\nIniciando o servidor. Feche esta janela para encerrar.\n")
    sys.path.insert(0, str(BACKEND))
    os.chdir(BACKEND)

    import uvicorn  # noqa: E402  (só após a checagem de dependências)

    try:
        uvicorn.run("servidor:app", host="127.0.0.1", port=porta, log_level="info")
    except KeyboardInterrupt:
        print("\nEncerrado pelo usuário.")
    return 0


if __name__ == "__main__":
    codigo = main()
    if codigo != 0:
        try:
            input("\nPressione Enter para fechar...")
        except EOFError:
            pass
    sys.exit(codigo)
