# Preference: finish product before testing

The user explicitly said: "我永远希望尽快做成成品再测".

Operational rule: when a workflow requires a usable installed/runnable artifact before meaningful testing, prefer getting to that productized state quickly, then test. Do not create circular gates where testing is required before the artifact can be installed or made usable. Distinguish "install for local hand testing" from "final release/live closure/commit"; local install/parity can be the prerequisite that makes testing possible, while final acceptance still follows after the user's hands-on test.
