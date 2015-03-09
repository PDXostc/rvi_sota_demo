# SOTA DEMO

Simple SOTA demo using RVI and our own backend server.

Please note that this demo has nothing to do with the RVI SOTA *product* effort, which can be found in its own [repo](https://github.com/PDXostc/rvi_sota)

# SETUP INSTRUCTIONS FOR SOTA DEMO ON TIZEN BOX #

**Please note that there is a bug in Tizen WRT where the
  wrt-installer regularly hangs the Tizen box when invoked to install
  the transmitted package. This will be fixed when we move to
  crosswalk.**

## SETUP

All files are available at rvi@rvi1.nginfotpdx.net:sota_demo/

Flash the tizen image TizenIVI30_APR22_AGL_19SEP2014.raw.gz

### Install RVI 
Once the new Tizen image has booted, install the RVI 0.3.0 rpm:

    rpm -i rvi-0.3.0-1.i686.rpm

### Install SOTA demo
The SOTA demo is provided as an RPM file:

    rpm -i sota_demo-0.3.0-1.i686.rpm

### Set Tizen box VIN number
Edit the RVI config file to install a VIN number.

    /opt/rvi-0.3.0/sys.config
	
Append the VIN number to the end of the node_service_prefix value:

Before:

      {node_service_prefix,"jlr.com/vin/"},

After:

      {node_service_prefix,"jlr.com/vin/9UYA31581L000000"},

Save the sys.config

### Install the new home screen

Install the updated home screen: intelPoc10.HomeScreen.wgt.20141025_1

    wrt-installer -un intelPoc10.HomeScreen
    wrt-installer -i intelPoc10.HomeScreen.wgt.20141027_1

## RUNNING

Reboot the Tizen box to bring up the RVI node and the SOTA demo



