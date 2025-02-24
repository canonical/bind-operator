[![CharmHub Badge](https://charmhub.io/bind/badge.svg)](https://charmhub.io/bind)
[![Publish to edge](https://github.com/canonical/dns-charms/actions/workflows/publish_charm.yaml/badge.svg)](https://github.com/canonical/dns-charms/actions/workflows/publish_charm.yaml)
[![Promote charm](https://github.com/canonical/dns-charms/actions/workflows/promote_charm.yaml/badge.svg)](https://github.com/canonical/dns-charms/actions/workflows/promote_charm.yaml)
[![Discourse Status](https://img.shields.io/discourse/status?server=https%3A%2F%2Fdiscourse.charmhub.io&style=flat&label=CharmHub%20Discourse)](https://discourse.charmhub.io)

# Bind Operator

A [Juju](https://juju.is/) [charm](https://juju.is/docs/olm/charmed-operators)
deploying and managing a DNS server on bare metal.

This charm simplifies configuration of a DNS server by providing a single point
of configuration for all the requirers using the same DNS server. It can be
deployed on virtual machines or bare metal.

As such, the charm makes it easy to manage and propagate DNS configuration, while
giving the freedom to deploy on the substrate of their choice.

For DevOps or SRE teams this charm will make operating any charm requiring dynamic DNS
configuration simple and straightforward through Juju's clean interface.

## Get started

The charm can be deployed to any machine model by pulling it from [charmhub](https://charmhub.io/bind):
```
juju deploy bind --channel=latest/edge
```

You can then integrate it with any charm supporting the requirer side of the `dns_record` interface and the bind operator will
start serving those DNS records.

### Basic operations

No actions are available as this charm is meant to be operated through its integrations.  
It can integrate with any requirer charm implementing the [dns_record interface](https://canonical.github.io/charm-relation-interfaces/interfaces/dns_record/v0/).

## Learn more
* [Read more](https://charmhub.io/bind/docs)
* [Official webpage](https://charmhub.io/bind)

## Project and community
* [Issues](https://github.com/canonical/dns-charms/issues)
* [Contributing](https://charmhub.io/bind/docs/how-to-contribute)
* [Matrix](https://chat.charmhub.io/charmhub/channels/charm-dev)
