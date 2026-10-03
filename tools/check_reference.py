"""Run a hand-written property test file against HumanEval's reference solution.

Usage: python tools/check_reference.py HumanEval/26 scratch/props_remove_duplicates.py
Every property you write should pass here; if one fails, the property (or its input
domain) is wrong, not the reference.
"""
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pbt.data import load_problems  # noqa: E402

task_id, test_file = sys.argv[1], Path(sys.argv[2])
problem = load_problems("data/HumanEval.jsonl.gz", "properties.yaml", [task_id])[0]
work = Path("scratch/reference") / problem.slug
work.mkdir(parents=True, exist_ok=True)
(work / "solution.py").write_text(problem.reference)
shutil.copy(test_file, work / "test_props.py")
command = [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_props.py"]
sys.exit(subprocess.run(command, cwd=work).returncode)
