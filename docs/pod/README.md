## Your very first pod

Now that we have a cluster up and running, we can start experimenting with Kubernetes by deploying a simple toy application. The easiest thing to start with is to run a single [pod](https://kubernetes.io/docs/concepts/workloads/pods/), which is essentially the most basic primitive you can create in Kubernetes. A pod is basically one or more containers, which are scheduled together to a single node. Often a pod consists of just one container, but by using multiple containers you can implement patterns like [sidecar containers](https://docs.microsoft.com/en-us/azure/architecture/patterns/sidecar).

### A simple application

To get the ball rolling, let's write a [trivial Python web application](/app/app.py) with Flask, which we'll deploy to the cluster as a pod:

```python
import platform

from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return {
        "host": platform.node()
    }
```

Even if you're not familiar with Flask, this should be rather easy to understand. When the application receives an HTTP GET request to `/`, it will return a JSON payload with the network name of the host.

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

> If you're running macOS, then k3d-my-cluster-registry might not be a reachable host, because containers are not automatically reachable from the macOS host. In that case you can just add the host as a new entry in  `/etc/hosts`, i.e. map k3d-my-cluster-registry to 127.0.0.1.

And now you've got your container image published and ready to go.

### Deploying the application as a pod

So by now we've written our application, containerized it and pushed the container image the registry. Next we'll need to whip up a simple pod definition `pod-example.yml`:

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

So the pod is now running within our cluster. How do we actually talk to it with say, something like curl? Pods for all intents and purposes do not really exist outside the cluster, but one of the many ways we can reach the pod and see if the HTTP API is actually responding is by creating yet another pod!

First, you want to grab the IP of our currently running pod:

```shell
$ kubectl get pods/pod-example -o json | jq '.status.podIP'

"10.42.0.6"
```

Note that this is the IP of the pod _within_ the cluster. You can't really reach it outside the cluster just yet. In order to communicate with it, we'll create a temporary [busybox](https://en.wikipedia.org/wiki/BusyBox) pod and use wget to send an HTTP request to our pod running Flask:

```shell
$ kubectl run -it busybox --image=busybox --rm --restart=Never -- wget -q -O - 10.42.0.6:5000

{"host":"pod-example"}
```

So our Flask app is actually up and running within the pod. Neat!
