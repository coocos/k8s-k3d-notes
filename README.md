# k8s-experiments

This repository contains notes and toy applications I've developed in order to grok using Kubernetes. I find writing things down in a blog'ish form helps me grasp and remember concepts better. These notes probably aren't useful for you but hey, who knows!

## Creating a cluster

First things first, you need a Kubernetes cluster to deploy your applications to. There are obviously a number of ways to go about this, but especially for local development [k3d](https://github.com/rancher/k3d) is a lightweight option for spinning up a multinode cluster on a single machine. Additionally, k3d ships with an optional [local container registry](https://k3d.io/usage/guides/registries/#using-a-local-registry), which you can use to distribute your custom container images within the cluster. If you're running MacOS, you can use [brew](https://github.com/Homebrew/brew) to install k3d:

```shell
$ brew install k3d
```

Then, create a simple cluster with one server node, one worker node and a container registry:

```shell
$ k3d cluster create my-cluster --servers 1 --agent 1 --registry-create
```

If everything went okay, now you should have a working cluster. You can verify this by:

```shell
$ kubectl cluster-info

Kubernetes master is running at https://0.0.0.0:50052
CoreDNS is running at https://0.0.0.0:50052/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy
Metrics-server is running at https://0.0.0.0:50052/api/v1/namespaces/kube-system/services/https:metrics-server:/proxy
```

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

Looking great!

## Your very first pod

Now that we have a cluster up and running, we can start experimenting with Kubernetes by deploying a simple toy application. The easiest thing to start with is to run a single [pod](https://kubernetes.io/docs/concepts/workloads/pods/), which is essentially the most basic primitive you can create in Kubernetes. A pod is basically one or more containers, which are scheduled together to a single node. Often a pod consists of just one container, but by using multiple containers you can implement patterns like [sidecar containers](https://docs.microsoft.com/en-us/azure/architecture/patterns/sidecar).

### A simple application

To get the ball rolling, let's write a [trivial Python web application](./pod-example/) with Flask, which we'll deploy to the cluster as a pod:

```python
import platform

from flask import Flask

app = Flask(__name__)


@app.route('/')
def home():
    return {
        "host": platform.node()
    }
```

Even if you're not familiar with Flask, this should be rather easy to understand. Essentially when we send an HTTP GET request to `/`, the application will return a JSON payload with the network name of the host.

### Containerizing the application

In order to deploy the application as a pod, we need to containerize it, so let's create a definitely-not-safe-for-production Dockerfile for it:

```dockerfile
FROM python:3.9-alpine

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["flask", "run", "--host", "0.0.0.0"]
```

And then we can build the image:

```shell
$ docker build -t pod-example:0.1 .
```

Now we have the container image built, but we haven't yet made the image available to the cluster. So let's push it to the container registry!

### Pushing the container image to registry

By default Kubernetes will attempt to pull your container images from Docker Hub, but since k3d provides you with a local registry, it's better to use that instead for your own experiments. The registry runs as a Docker container and you can grab its port like this (or just use `docker ps`):

```shell
$ docker inspect k3d-my-cluster-registry | jq '.[0].NetworkSettings.Ports'

{
  "5000/tcp": [
    {
      "HostIp": "0.0.0.0",
      "HostPort": "50785"
    }
  ]
}
```

So let's tag our image and push it to the registry, using the port we just grabbed:

```shell
$ docker tag pod-example k3d-my-cluster-registry:50785/pod-example:0.1
$ docker push k3d-my-cluster-registry:50785/pod-example:0.1
```

> If you're running MacOS, then k3d-my-cluster-registry might not be a reachable host, because container IPs are not automatically reachable from the MacOS host. In that case you can just add the host as a new entry in /etc/hosts, i.e. map k3d-my-cluster-registry to 127.0.0.1.

And hopefully things went smoothly.

### Deploying the application as a pod

So by now we've got our application written, containerized and pushed to the registry. Next we'll need to whip up a simple pod definition `pod-example.yml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  labels:
    app: example
  name: pod-example
spec:
  containers:
  - image: k3d-my-cluster-registry:50785/pod-example:0.1
    name: pod-example
```

Note that the container image refers to the registry, where you pushed your image to and not Docker Hub. All the nodes within the cluster should be able to access this registry. Next, you can run `kubectl apply -f pod-example.yml` to start the pod. If you run `kubectl get pods` shortly afterwards, you should see your pod either running or being created:

```
NAME          READY   STATUS    RESTARTS   AGE
pod-example   1/1     Running   0          5m2s
```

You can also check its logs with `kubectl logs pod-example` or inspect the pod in more detail with `kubectl describe pods/pod-example`.

### Talking to the pod

So the pod is now running within our cluster. How do we actually talk to it with say, something like curl? Pods for all intents and purposes do not really exist outside the cluster, but one way we can reach the pod and see if the HTTP API is actually responding is by creating yet another pod!

First, you want to grab the IP of our currently running pod:

```shell
$ kubectl get pods/pod-example -o json | jq '.status.podIP'

"10.42.0.6"
```

Note that this is the IP of the pod _within_ the cluster. You can't really reach it outside the cluster just yet. In order to communicate with it, let's create a temporary [busybox](https://en.wikipedia.org/wiki/BusyBox) pod and use wget to send an HTTP request to our pod running Flask:

```shell
$ kubectl run -it busybox --image=busybox --rm --restart=Never -- wget -q -O - 10.42.0.6:5000

{"host":"pod-example"}
```

So our Flask app is actually up and running within the pod. Neat!

## Why settle for one?

Currently our Flask application is running in a single pod. If you delete the pod using `kubectl delete pods/pod-example`, then that particular pod and the application as a whole is gone. Kubernetes neither re-creates the pod nor runs multiple replicas of it by default. To do that, you need to use a [ReplicaSet](https://kubernetes.io/docs/concepts/workloads/controllers/replicaset/). ReplicaSets essentially allow you to define how many copies of a stateless application you want and delegate the details to Kubernetes. Kubernetes will monitor how many replicas are running at a given time and if there are too many or too few, it will correct the situation by scheduling more pods to nodes or deleting excess pods.

### Creating a ReplicaSet

So how do we create a ReplicaSet? Once again, YAML to the rescue:

```yaml
apiVersion: apps/v1
kind: ReplicaSet
metadata:
    name: example-replica-set
    labels:
        app: example
spec:
    replicas: 3
    selector:
        matchLabels:
            app: example
    template:
        metadata:
            labels:
                app: example
        spec:
            containers:
                - name: example
                  image: k3d-my-cluster-registry:50785/pod-example:0.1
```

What this definition essentially states is that the ReplicaSet will create three pods, all of which will run our Flask application. It will also assign a label named `app` with a value of `example` to each of our pods, which is a key thing. ReplicaSets work by using these labels to select a set pods to be the replicas. This is defined with the `matchLabels` attribute. If there aren't enough of pods with matching labels, then the ReplicaSet will create more. If there are too many, then it will delete some.

Now let's get cracking and create our ReplicaSet:

```shell
$ kubectl apply -f replica-set.yml
```

Afterwards you should be able to view the ReplicaSet:

```shell
$ kubectl get rs

NAME                  DESIRED   CURRENT   READY   AGE
example-replica-set   3         3         3       12m
```

### Replicated pods

You can also view the pods themselves:

```
$ kubectl get pods --show-labels

NAME                        READY   STATUS    RESTARTS   AGE     LABELS
example-replica-set-zcj8p   1/1     Running   0          5m32s   app=example
example-replica-set-rc4kf   1/1     Running   0          5m32s   app=example
example-replica-set-nz48n   1/1     Running   0          5m32s   app=example
```

If you take a closer look at a them, you might also notice that some of them have been scheduled to different nodes:

```shell
$ kubectl describe pods | egrep -i 'Node:|IP:'

Node:         k3d-my-cluster-agent-0/172.18.0.3
IP:           10.42.1.15
Node:         k3d-my-cluster-server-0/172.18.0.4
IP:           10.42.0.26
Node:         k3d-my-cluster-server-0/172.18.0.4
IP:           10.42.0.27
```

Now let's test deleting a single pod and seeing what happens:

```shell
$ kubectl delete pods/example-replica-set-nz48n

pod "example-replica-set-nz48n" deleted

$ kubectl get pods --show-labels

NAME                        READY   STATUS    RESTARTS   AGE     LABELS
example-replica-set-zcj8p   1/1     Running   0          8m10s   app=example
example-replica-set-rc4kf   1/1     Running   0          8m10s   app=example
example-replica-set-tlpnw   1/1     Running   0          46s     app=example
```

And sure enough, the ReplicaSet created a new pod to replace our deleted one! You can also see this happening if you take a look at the ReplicaSet events:

```shell
$ kubectl describe rs/example-replica-set | grep -A 6 Events

Events:
  Type    Reason            Age    From                   Message
  ----    ------            ----   ----                   -------
  Normal  SuccessfulCreate  10m    replicaset-controller  Created pod: example-replica-set-rc4kf
  Normal  SuccessfulCreate  10m    replicaset-controller  Created pod: example-replica-set-nz48n
  Normal  SuccessfulCreate  10m    replicaset-controller  Created pod: example-replica-set-zcj8p
  Normal  SuccessfulCreate  3m19s  replicaset-controller  Created pod: example-replica-set-tlpnw
```

### Routing traffic to replicated pods

By now we have multiple replicas of our toy application running. How do we go about routing traffic to them though? We know the IPs of the pods, but these IPs can change as pods are deleted and created due to nodes crashing and whatnot. How can we reach these ephemeral pods in a reliable manner? Enter services.

## Service please

## Deployments
