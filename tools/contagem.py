#!/usr/bin/env python3
"""Count the tests, and hold the README to what it says.

WHY THIS EXISTS.

The README states the number of tests in three places: a badge, a comment next
to the pytest command, and a line in the file table. Three copies of one fact,
and nothing re-measuring any of them.

They drifted. The suite grew and the numbers stayed where they were -- nobody lied
and nobody noticed, which is exactly the problem with a number typed into prose.
It is a measurement with no instrument behind it, and it starts decaying the
moment it is written. The same failure, on a bigger number, is how the sibling
portfolio repository spent months claiming a Lighthouse score it did not have.

This is the instrument.

    python3 tools/contagem.py            check
    python3 tools/contagem.py --fix      rewrite the README with the real number

It reads *every* number the README states rather than matching three known
phrasings, because a guard that only knows the sentences it was written against
stops guarding the moment somebody rewords one.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
README = RAIZ / "README.md"

# Cada sítio onde um número de testes pode aparecer, e como se lê.
#   - o crachá do shields.io:            badge/tests-32-brightgreen
#   - o texto alternativo do crachá:     ![32 tests](
#   - qualquer "N tests" em prosa ou numa tabela
PADROES = (
    re.compile(r"badge/tests-(\d+)-"),
    re.compile(r"(\d+) tests?\b"),
)


def contar() -> int:
    """Quantos testes a suite tem, perguntando ao pytest em vez de adivinhar."""
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-header"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
    )
    m = re.search(r"^(\d+) tests? collected", r.stdout, re.M)
    if not m:
        # Falhar alto. Um zero silencioso faria esta verificação passar
        # precisamente no momento em que deixou de funcionar.
        print("contagem: nao consegui contar os testes. Saida do pytest:")
        print((r.stdout + r.stderr).strip()[-800:])
        raise SystemExit(1)
    return int(m.group(1))


def main() -> int:
    corrigir = "--fix" in sys.argv[1:]
    real = contar()
    texto = README.read_text(encoding="utf-8")

    encontrados: list[tuple[int, int, int]] = []  # (inicio, fim, valor)
    for padrao in PADROES:
        for m in padrao.finditer(texto):
            encontrados.append((m.start(1), m.end(1), int(m.group(1))))

    if not encontrados:
        print("contagem: o README deixou de dizer quantos testes ha.")
        return 1

    errados = [e for e in encontrados if e[2] != real]
    if not errados:
        print(f"contagem: {real} testes — o README bate certo em {len(encontrados)} sitios")
        return 0

    if not corrigir:
        for _, _, valor in errados:
            print(f"contagem: o README diz {valor} testes; sao {real}.")
        print("        Corrige com:  python3 tools/contagem.py --fix")
        return 1

    # De trás para a frente, para que substituir não desloque os índices
    # seguintes.
    for inicio, fim, valor in sorted(errados, reverse=True):
        texto = texto[:inicio] + str(real) + texto[fim:]
    README.write_text(texto, encoding="utf-8")
    print(f"contagem: README posto a {real} testes ({len(errados)} sitios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
