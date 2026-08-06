import re
from pathlib import Path
from typing import List, Dict


CLAUSE_PATTERN = re.compile(
    r"=== CLAUSE START ===\s*"
    r"ID:\s*(?P<id>.*?)\s*"
    r"SECTION:\s*(?P<section>.*?)\s*"
    r"TEXT:\s*(?P<text>.*?)\s*"
    r"=== CLAUSE END ===",
    re.DOTALL,
)


def load_clauses(path: str | Path) -> List[Dict[str, str]]:
    content = Path(path).read_text(encoding="utf-8")
    clauses = []

    for match in CLAUSE_PATTERN.finditer(content):
        clauses.append(
            {
                "id": match.group("id").strip(),
                "section": match.group("section").strip(),
                "text": match.group("text").strip(),
            }
        )

    return clauses


if __name__ == "__main__":
    clauses = load_clauses("data/input/regulations.txt")
    for clause in clauses:
        print(clause)