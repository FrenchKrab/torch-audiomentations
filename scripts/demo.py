import os
import random
from pathlib import Path

import librosa
import numpy as np
import time
import torch
from scipy.io import wavfile

from torch_audiomentations import (
    PolarityInversion,
    Gain,
    PeakNormalization,
    Compose,
    Shift,
    AddBackgroundNoise,
    ApplyImpulseResponse,
    TimeStretch)

SAMPLE_RATE = 44100

BASE_DIR = Path(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
SCRIPTS_DIR = BASE_DIR / "scripts"
TEST_FIXTURES_DIR = BASE_DIR / "test_fixtures"


class timer(object):
    """
    timer: A class used to measure the execution time of a block of code that is
    inside a "with" statement.

    Example:

    ```
    with timer("Count to 500000"):
        x = 0
        for i in range(500000):
            x += 1
        print(x)
    ```

    Will output:
    500000
    Count to 500000: 0.04 s

    Warning: The time resolution used here may be limited to 1 ms
    """

    def __init__(self, description="Execution time", verbose=False):
        self.description = description
        self.verbose = verbose
        self.execution_time = None

    def __enter__(self):
        self.t = time.time()
        return self

    def __exit__(self, type, value, traceback):
        self.execution_time = time.time() - self.t
        if self.verbose:
            print("{}: {:.3f} s".format(self.description, self.execution_time))


if __name__ == "__main__":
    """
    For each transformation, apply it to an example sound and write the transformed sounds to
    an output folder. Also crudely measure and print execution time.
    """
    output_dir = os.path.join(SCRIPTS_DIR, "demo_output")
    os.makedirs(output_dir, exist_ok=True)

    np.random.seed(42)
    random.seed(42)

    filenames = ["perfect-alley1.ogg", "perfect-alley2.ogg"]
    samples1, _ = librosa.load(
        os.path.join(TEST_FIXTURES_DIR, filenames[0]), sr=SAMPLE_RATE, mono=False
    )
    samples2, _ = librosa.load(
        os.path.join(TEST_FIXTURES_DIR, filenames[1]), sr=SAMPLE_RATE, mono=False
    )
    samples = np.stack((samples1, samples2), axis=0)
    samples = torch.from_numpy(samples)

    modes = ["per_batch", "per_example", "per_channel"]
    for mode in modes:
        transforms = [
            {
                "instance": AddBackgroundNoise(
                    background_paths=TEST_FIXTURES_DIR / "bg", mode=mode, p=1.0
                ),
                "num_runs": 5,
            },
            {
                "instance": ApplyImpulseResponse(
                    ir_paths=TEST_FIXTURES_DIR / "ir", mode=mode, p=1.0
                ),
                "num_runs": 1,
            },
            {
                "instance": Compose(
                    transforms=[
                        Gain(
                            min_gain_in_db=-18.0, max_gain_in_db=-16.0, mode=mode, p=1.0
                        ),
                        PeakNormalization(mode=mode, p=1.0),
                    ],
                    shuffle=True,
                ),
                "name": "Shuffled Compose with Gain and PeakNormalization",
                "num_runs": 5,
            },
            {
                "instance": Compose(
                    transforms=[
                        Gain(
                            min_gain_in_db=-18.0, max_gain_in_db=-16.0, mode=mode, p=0.5
                        ),
                        PolarityInversion(mode=mode, p=0.5),
                    ],
                    shuffle=True,
                ),
                "name": "Compose with Gain and PolarityInversion",
                "num_runs": 5,
            },
            {"instance": Gain(mode=mode, p=1.0), "num_runs": 5},
            {"instance": PolarityInversion(mode=mode, p=1.0), "num_runs": 1},
            {"instance": PeakNormalization(mode=mode, p=1.0), "num_runs": 1},
            {"instance": Shift(mode=mode, p=1.0), "num_runs": 5},
            {"instance": TimeStretch(mode=mode, p=1.0), "num_runs": 5},
        ]

        execution_times = {}

        for transform in transforms:
            augmenter = transform["instance"]
            transform_name = (
                transform.get("name")
                if transform.get("name")
                else transform["instance"].__class__.__name__
            )
            execution_times[transform_name] = []
            for i in range(transform["num_runs"]):
                with timer() as t:
                    augmented_samples = augmenter(
                        samples=samples, sample_rate=SAMPLE_RATE
                    ).numpy()
                execution_times[transform_name].append(t.execution_time)
                for example_idx, original_filename in enumerate(filenames):
                    output_file_path = os.path.join(
                        output_dir,
                        "{}_{}_{:03d}_{}.wav".format(
                            transform_name, mode, i, Path(original_filename).stem
                        ),
                    )
                    wavfile.write(
                        output_file_path,
                        rate=SAMPLE_RATE,
                        data=augmented_samples[example_idx].transpose(),
                    )

        for transform_name in execution_times:
            if len(execution_times[transform_name]) > 1:
                print(
                    "{:<52} {:.3f} s (std: {:.3f} s)".format(
                        transform_name,
                        np.mean(execution_times[transform_name]),
                        np.std(execution_times[transform_name]),
                    )
                )
            else:
                print(
                    "{:<52} {:.3f} s".format(
                        transform_name, np.mean(execution_times[transform_name])
                    )
                )
