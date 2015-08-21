# SOTA DEMO

Simple SOTA demo using RVI and our own backend server.

**Please note that this demo has nothing to do with the RVI SOTA reference implementation project, which can be found in its own [server](https://github.com/PDXostc/rvi_sota_server) and [client](https://github.com/PDXostc/rvi_sota_client) repos.**

# SETUP INSTRUCTIONS FOR SOTA DEMO ON TIZEN BOX #


## SETUP

All files are available at rvi@rvi1.nginfotpdx.net:sota_demo/

Flash the latest stable JLR AGL Tizen image

### Install RVI 
Once the new Tizen image has booted, install the RVI 0.4.0 rpm:

    rpm -i rvi-0.4.0-1.i686.rpm

### Install SOTA demo
The SOTA demo is provided as an RPM file:

    rpm -i sota_demo-0.3.0-1.i686.rpm

### Set Tizen VIN

1. Reboot the Tizen box
2. Bring up settings
3. Bring up RVI Settings
4. Enter a unique VIN string
5. Reboot the Tizen box to make the changes take effect

### Backend - Setup vehicle security key
1. Surf to ```rvi1.nginfotpdx.net:8000```
2. Click on Administration
3. Click on Add Key
4. Enter the VIN + "\_key" from step 4 of Set Tizen VIN above ```sotademo_key```
5. Enter the current date and time in the Valid From section
6. Enter a date and time one year from now in the Valid To section
7. Enter ```123``` as key PEM.
8. Click save

### Backend - Setup vehicle

1. Surf to ```rvi1.nginfotpdx.net:8000```
2. Click on Administration
3. Click on Add Vehicle
4. Enter a vehicle make
5. Enter a vehicle model
6. Enter the vehicle VIN specified in step 4 of the Tizen setup box procedure
7. Select account ```admin```
8. Enter RVI domain ```jlr.com```
9. Select the key created in the vehicle security key procedure above
10. Click save


## RUN THE DEMO - BACKEND
1. Surf to ```rvi1.nginfotpdx.net:8000``` 
2. Login using RVI-provided credentials
3. Click on Administration
4. Click on Add SOTA Update
5. Select the vehicle created in the Setup vehicle procedure above
6. Select package ```Audio Settings 1.0```
7. Select a Valid until date one day from the current time
8. Enter 1 as the maximum retries
9. Click save
10. Select the newly created update 
11. Select action ```Start selected updates``` 
12. Click Go

## RUN THE DEMO - TIZEN
1. Confirm the download on the popup
2. Wait for download and install to complete
3. Bring up audio manager to see stripped version without 3D controls

