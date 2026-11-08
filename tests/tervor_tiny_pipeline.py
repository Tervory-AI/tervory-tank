"""Exercise Tank's training worker; all model loading remains inside Tank."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tank.training_jobs import tiny_proof

if __name__ == '__main__':
    tiny_proof.main()
