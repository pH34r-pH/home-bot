# Working on Home Bot

- Keep the project free to run locally. Do not introduce paid APIs or hosted dependencies.
- Preserve the Pixel-as-brain and Arduino-Mega-as-actuator-controller architecture.
- Keep simulator truth in test/evaluation code. Runtime observations must match the available hardware.
- Record uncertain dimensions, servo models, limits and electrical interfaces as unmeasured. Never invent pinouts or calibration constants.
- Keep actuator units explicit: meters, seconds and radians. Android IMU coordinates differ from the chassis frame.
- Keep original assets Apache-2.0 compatible. Do not copy Webots-only robot assets into this repository.
- After control changes, run `python -m unittest discover -s tests -v`.
- After config/model changes, regenerate worlds, run `python scripts/build_worlds.py --check`, and run `scripts/run_smoke.py` with Webots if installed.
- Validate operator-panel changes against the running simulator. Do not claim Android, firmware, autonomous navigation, or real-world transfer is validated by simulator tests.
