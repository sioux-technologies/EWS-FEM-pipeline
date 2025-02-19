import logging
import multiprocessing
import os
import re
import shutil
import subprocess
from enum import Enum
from functools import partial
from multiprocessing.pool import ThreadPool
from pathlib import Path

from tqdm import tqdm

from ews_fem_pipeline.febio_settings import Settings

logger = logging.getLogger(__name__)


class FEBioRunner:
    febio_executable: Path | None = None

    def __init__(self):
        self.resolve_febio_executable()

    def resolve_febio_executable(self):
        # Look for environment variable FEBIO_PATH: if that exists, it should point towards the executable
        # (or folder with executable); if it doesn't exist, look for it on the path, or some other default locations
        if "FEBIO_PATH" in os.environ:
            febio_path = Path(os.environ["FEBIO_PATH"])
            logger.debug(f"Looking for febio on the FEBIO_PATH: {febio_path}.")

            if febio_path.is_dir():
                febio_path /= Settings.febio_default_exe_name

            self.febio_executable = febio_path


        # Look on path (extended by some default search directories)
        else:
            logger.debug("Looking for febio on the (extended) system path.")
            search_path = os.environ["PATH"]
            search_path = os.pathsep.join([search_path, *Settings.febio_search_path_extension])
            febio_path = shutil.which("febio4.exe", path=search_path)

            if febio_path is not None:
                self.febio_executable = Path(febio_path)

        if self.febio_executable is not None:
            logger.debug(f"Found FEBio executable: {self.febio_executable}.")
        else:
            logger.error("Did not find FEBio executable.")
            raise FileNotFoundError("Did not find FEBio executable.")

    def run(self, input_files: tuple[Path, ...], n_processes: int = 1):
        assert all(f.is_file() for f in input_files)
        assert n_processes >= 1

        run_fn = partial(self.run_simulation, allow_OMP=(n_processes == 1))
        progbar = partial(tqdm, total=len(input_files), ncols=80)

        if n_processes == 1:
            list(progbar(map(run_fn, input_files)))
        else:
            with ThreadPool(n_processes) as pool:
                list(progbar(pool.imap(run_fn, input_files)))

        logger.info("\n# Finished, checking all result files")

        output_files = []
        # Check all resulting files
        for input_file in input_files:
            state, total_time = self.check_termination(input_file)
            logger.info(state.format(name=input_file.name, time=total_time))

            if state == FEBioRunner.TERMINATIONSTATES.NORMALTERMINATION:
                output_files.append(input_file)
        return tuple(output_files)

    def run_simulation(self, input_file: Path, allow_OMP: bool = True):
        run_logger = logging.getLogger(__name__)
        env = os.environ.copy()

        # Allow parallelization by FEBio
        env["OMP_NUM_THREADS"] = str(multiprocessing.cpu_count()) if allow_OMP else "1"

        run_logger.info(f"Started running {input_file.name}")

        proc_args = [str(self.febio_executable), str(input_file)]
        run_logger.debug(" " + " ".join(proc_args))

        p = subprocess.Popen(proc_args, env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p.wait()

    # Info for reading end of the log file
    TAIL_LENGTH = 120  # bytes to read from end of file

    class TERMINATIONSTATES(str, Enum):
        NORMALTERMINATION = "{name} terminated successfully in {time} seconds."
        ERRORTERMINATION = "{name} terminated unsuccessfully in {time} seconds."
        NOTERMINATION = "{name} terminated unexpectedly (no termination state found)."
        NOLOGFILE = "{name} most likely didn't run (no log file found)."

    TERMINATIONPATTERNS: tuple[tuple[TERMINATIONSTATES, re.Pattern], ...] = (
        (TERMINATIONSTATES.NORMALTERMINATION, re.compile("N O R M A L {3}T E R M I N A T I O N")),
        (TERMINATIONSTATES.ERRORTERMINATION, re.compile("E R R O R {3}T E R M I N A T I O N")),
    )

    TIMEPATTERN = re.compile(r"Total elapsed time [.]* : [\d:]* \(([\d.]*) sec\)")

    def check_termination(self, input_file: Path) -> tuple[TERMINATIONSTATES, float]:
        logfile = input_file.with_suffix(".log")

        total_time = -1
        term_state = self.TERMINATIONSTATES.NOTERMINATION

        if not logfile.is_file():
            term_state = self.TERMINATIONSTATES.NOLOGFILE
            return term_state, total_time

        with open(logfile, "rb") as file:
            # Read 100 byes from end of file
            file.seek(-self.TAIL_LENGTH, 2)
            tail = file.read(self.TAIL_LENGTH).decode("utf-8")

            for state, pattern in self.TERMINATIONPATTERNS:
                if pattern.search(tail):
                    term_state = state
                    break

            if match := self.TIMEPATTERN.search(tail):
                total_time = float(match.group(1))

        return term_state, total_time
