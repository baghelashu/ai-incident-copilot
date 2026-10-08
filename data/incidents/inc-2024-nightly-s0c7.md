# Past incident: Nightly settlement batch failed with S0C7

## Summary
Nightly settlement job SETLJ010 abended in step STEP020 and held 12 downstream jobs.

## Root cause
An upstream file contained spaces in the packed-decimal AMOUNT field, causing ABEND S0C7 in program SETL200.

## Resolution
The bad record was corrected in the input dataset and the job restarted from STEP020. Input
validation was added to the upstream extract job.
