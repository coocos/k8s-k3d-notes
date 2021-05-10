## Creating a cluster

First things first, you need a Kubernetes cluster to deploy your applications to. There are obviously a number of ways to go about this, but especially for local development k3d is a lightweight option for spinning up a multinode cluster on a single machine. Additionally, k3d ships with an optional [local container registry](https://k3d.io/usage/guides/registries/#using-a-local-registry), which you can use to distribute your custom container images within the cluster. If you're running macOS, you can use [brew](https://github.com/Homebrew/brew) to install k3d:

```shell
$ brew install k3d
```

Then, create a simple cluster with one server node, one worker node and a container registry:

```shell
$ k3d cluster create my-cluster --servers 1 --agents 1 --registry-create
```

If everything went okay, now you should have a working cluster. You can verify this with `kubectl`:

```shell
$ kubectl cluster-info

Kubernetes master is running at https://0.0.0.0:50052
CoreDNS is running at https://0.0.0.0:50052/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy
Metrics-server is running at https://0.0.0.0:50052/api/v1/namespaces/kube-system/services/https:metrics-server:/proxy
```

> If you haven't got kubectl installed, you can grab it [from here](https://kubernetes.io/docs/tasks/tools/).

You can also check the state of the nodes you created:

```
$ kubectl get nodes

NAME                            STATUS   ROLES                  AGE     VERSION
k3d-my-cluster-agent-0    Ready    <none>                 4m3s    v1.20.6+k3s1
k3d-my-cluster-server-0   Ready    control-plane,master   4m15s   v1.20.6+k3s1
```

Since k3d actually runs everything in Docker containers, you can also check the containers themselves:

```
$ docker ps

CONTAINER ID   IMAGE                      COMMAND                  CREATED         STATUS         PORTS                             NAMES
47004e4a19c2   rancher/k3d-proxy:v4.4.2   "/bin/sh -c nginx-pr…"   2 minutes ago   Up 2 minutes   80/tcp, 0.0.0.0:50857->6443/tcp   k3d-my-cluster-serverlb
cb05365719fe   rancher/k3s:latest         "/bin/k3s agent"         2 minutes ago   Up 2 minutes                                     k3d-my-cluster-agent-0
81ea537a1262   rancher/k3s:latest         "/bin/k3s server --t…"   2 minutes ago   Up 2 minutes                                     k3d-my-cluster-server-0
7158a5695881   registry:2                 "/entrypoint.sh /etc…"   2 minutes ago   Up 2 minutes   0.0.0.0:50858->5000/tcp           k3d-my-cluster-registry
```

So we have one container for the server node, one for the agent node, one for a load balancer and one for a container registry. Great!
