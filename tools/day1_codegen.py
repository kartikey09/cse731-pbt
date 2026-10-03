"""Day 1 check: generate solution.py for every unit, then run HumanEval's own tests on it.

Usage: python tools/day1_codegen.py [ollama|openrouter]
Responses are cached, so the full pipeline on Day 2 reuses this code at no extra cost.
"""
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pbt.codegen_agent import CodeGenAgent           # noqa: E402
from pbt.data import load_problems                   # noqa: E402
from pbt.llm import LLM, load_dotenv                 # noqa: E402

load_dotenv()
cfg = yaml.safe_load(Path("config.yaml").read_text())
provider = sys.argv[1] if len(sys.argv) > 1 else cfg["provider"]
out = Path("runs/day1")
agent = CodeGenAgent(LLM(cfg["providers"][provider], out / "llm_log.jsonl"), cfg["agents"]["code_gen"])

for p in load_problems(cfg["pipeline"]["dataset"], cfg["pipeline"]["properties_file"]):
    src = agent.run(p)
    (out / p.slug).mkdir(parents=True, exist_ok=True)
    (out / p.slug / "solution.py").write_text(src)
    program = f"{src}\n\n{p.check}\n\ncheck({p.entry_point})\n"
    ok = subprocess.run([sys.executable, "-c", program], capture_output=True, timeout=30).returncode == 0
    print(f"{p.task_id:<14} {p.entry_point:<18} HumanEval tests: {'pass' if ok else 'FAIL'}")
