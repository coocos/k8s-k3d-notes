# k8s-k3d-notes

This repository contains notes I've written while getting familiar with Kubernetes using [k3d](https://github.com/rancher/k3d). I find writing things down in a blog'ish tutorial form helps me grasp concepts better. These notes probably aren't useful for you but hey, who knows!

These notes cover the following things:

- how to get started with Kubernetes by creating a development cluster using k3d
- how to publish a container image to the cluster container registry
- creating a Pod using the published container image
- using ReplicaSets to run multiple copies of a Pod
- routing internal and external traffic to Pods using Services
- using Deployments to scale and rollout Pods
- exposing services using an Ingress

Plenty of Kubernetes concepts are not covered here, including ConfigMaps, Secrets, DaemonSets, CronJobs, PersistentVolumes and many other things. Please see the [Kubernetes documentation](https://kubernetes.io/docs/concepts/) for more information.

The examples were tested with the following:

- kubectl 1.19.7
- k3d 4.4.2

## How to use these notes

These notes were written to be read in the following order:

1. [Creating a cluster](docs/cluster/README.md) - how to get started with Kubernetes
2. [Your very first pod](docs/pod/README.md) - deploying a simple application as a Pod
3. [Why settle for one?](docs/replicaset/README.md) - creating replicas using ReplicaSets
4. [Service please!](docs/service/README.md) - routing traffic to pods using Services
5. [Deployments](docs/deployment/README.md) - updating pods with Deployments
6. [Ingress](docs/ingress/README.md) - routing traffic to services from outside the cluster

In addition to this six part primer on commonly used Kubernetes primitives, there are also other notes which delve into further concepts. These can be read in no particular order:

- [Jobs](docs/job/README.md) - executing one-off tasks using Jobs
