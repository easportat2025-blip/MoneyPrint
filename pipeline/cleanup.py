import shutil
from pathlib import Path


def purge(*paths: Path) -> list[str]:
    removed = []
    for p in paths:
        if p is None:
            continue
        try:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
                removed.append(str(p))
            elif p.exists():
                p.unlink()
                removed.append(str(p))
        except OSError:
            pass
    return removed


def job_workdir(path: Path) -> list[str]:
    return purge(path)
