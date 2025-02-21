# Bind Snap

This snap is meant to be the workload of the [bind-operator](https://github.com/canonical/bind-operator) charm.  

## Installing the Snap
The snap can be installed directly from the Snap Store. Follow the link below for more information.  

[![Get it from the Snap Store](https://snapcraft.io/static/images/badges/en/snap-store-black.svg)](https://snapcraft.io/charmed-bind)


## Building the Snap
The steps outlined below are based on the assumption that you are building the snap with the latest LTS of Ubuntu.  If you are using another version of Ubuntu or another operating system, the process may be different.

### Clone Repository
```bash
git clone git@github.com:canonical/charmed-bind.git
cd charmed-bind
```
### Installing and Configuring Prerequisites
```bash
sudo snap install snapcraft
sudo snap install lxd
sudo lxd init --auto
```
### Packing and Installing the Snap
```bash
snapcraft pack
sudo snap install ./charmed-bind_*.snap --devmode
```
