MPSH files are what originally highlighted the numerical error in calculating
things about spacing because the timestamp for MPSH are exactly on the second.

In addition to what's tested in the other bound, there was also an issue with 
chopping the a file when the bound came in the middle of a file.

This test ensures the proper behavior is observed for that case.

