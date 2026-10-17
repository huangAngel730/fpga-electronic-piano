# R08-SW-R integration cases

Status: `SOURCE_READY_NOT_RUN`. This adapter contains 12 new R6-3 cases, 11 new R6-5 cases, four FRAME_PLAN boundary cases and two cross-package cases. It imports only production candidates when `run_case` is called, preserves `r07_fix` bytes, and does not import old selftests or runners. Execution belongs exclusively to the coordinator's single bounded R group.
