Summary:    Remote Vehicle Interaction - SOTA Demo packaging
Name:       rvi_sota_demo
Version:    0.3.0
Release:    1
Group:      App Framework/Application Communication
License:    Mozilla Public License 2.0
Source:     http://content.linuxfoundation.org/auto/downloads/rvi_sota_demo/rvi_sota_demo-0.3.0.tgz

BuildRequires:  make
BuildRequires:  python
BuildRequires:  rpm

%description 
SOTA Demo running on top of RVI


%prep
%setup -c rvi_sota_demo-$RPM_PACKAGE_VERSION

%build

%install
# Install the code.

rm -fr $RPM_BUILD_ROOT/opt/rvi_sota_demo-$RPM_PACKAGE_VERSION
mkdir -p $RPM_BUILD_ROOT/opt/rvi_sota_demo-$RPM_PACKAGE_VERSION

cp -r ./mod $RPM_BUILD_ROOT/opt/rvi_sota_demo-$RPM_PACKAGE_VERSION
cp ./rvi_json_rpc_server.py $RPM_BUILD_ROOT/opt/rvi_sota_demo-$RPM_PACKAGE_VERSION
cp ./sota_device.py $RPM_BUILD_ROOT/opt/rvi_sota_demo-$RPM_PACKAGE_VERSION

# Setup systemd
mkdir -p $RPM_BUILD_ROOT/usr/lib/systemd/system/
mkdir -p $RPM_BUILD_ROOT/etc/systemd/system/multi-user.target.wants/
install ./sota.service $RPM_BUILD_ROOT/usr/lib/systemd/system/sota.service
ln -fsr $RPM_BUILD_ROOT/usr/lib/systemd/system/sota.service $RPM_BUILD_ROOT/etc/systemd/system/multi-user.target.wants/sota.service
###################



%post
/usr/bin/systemctl daemon-reload

%postun

%clean
rm -rf $RPM_BUILD_ROOT

%files 
%manifest packaging/rvi_sota_demo.manifest 
%defattr(-,root,root)
/usr/lib/systemd/system/sota.service 
/etc/systemd/system/multi-user.target.wants/sota.service
/opt/rvi_sota_demo-0.3.0

