# TIZEN GIT BUILD SYSTEM (GBS) 

This file contains the spec files used to create a Tizen RPM through
gbs (Git Build System).

# PREPARATION
See the RVI Tizen build
[documentation](https://github.com/PDXostc/rvi/blob/master/packaging/README.md)
for instructions

# BUILDING
Go to the top directory of RVI SOTA demo and execute:

    sudo gbs build -A i586

An RPM file will be generated at the end of the build which can be
installed on a Tizen box. The RPM can be found at:

    ~/GBS-ROOT/local/repos/tizen/i586/RPMS/rvi-sota-0.3.0-1.i686.rpm





