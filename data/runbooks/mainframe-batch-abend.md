# Runbook: Mainframe batch job abend (S0C7 / S322 / S806)

## Symptoms
- Batch job ends with `ABEND S0C7`, `S322`, `S806` or a non-zero condition code (RC=12/16)
- Downstream jobs in the schedule are held and nightly files are missing

## Root cause
- `S0C7`: data exception, a packed-decimal field contains non-numeric data (bad input record).
- `S322`: job exceeded its CPU time limit (loop or unusually large input).
- `S806`: load module not found, wrong STEPLIB or program not promoted.

## Resolution
1. Open the job's SYSOUT/JESMSGLG to get the failing step, program and offset.
2. For S0C7, locate the bad record from the input dataset and correct or skip it, then restart from the failing step.
3. For S322, check input volume and raise TIME on the step only if volume is legitimate.
4. For S806, verify the STEPLIB/JOBLIB concatenation and that the module exists in the load library.
5. Release held downstream jobs once the step completes successfully.
