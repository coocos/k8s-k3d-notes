# k8s-k3d-notes

This repository contains notes I've written while getting familiar with Kubernetes using [k3d](https://github.com/rancher/k3d). I find writing things down in a blog'ish tutorial form helps me grasp concepts better. These notes probably aren't useful for you but hey, who knows!

These notes cover the following things:

* how to get started with Kubernetes by creating a development cluster using k3d
* how to publish a container image to the cluster container registry
* creating a Pod using the published container image
* using ReplicaSets to run multiple copies of a Pod
* routing internal and external traffic to Pods using Services
* using Deployments to scale and rollout Pods
* exposing services using an Ingress

Plenty of Kubernetes concepts are not covered here, including ConfigMaps, Secrets, DaemonSets, Jobs, CronJobs, PersistentVolumes and many other things. Please see the [Kubernetes documentation](https://kubernetes.io/docs/concepts/) for more information.

## Creating a cluster

First things first, you need a Kubernetes cluster to deploy your applications to. There are obviously a number of ways to go about this, but especially for local development k3d is a lightweight option for spinning up a multinode cluster on a single machine. Additionally, k3d ships with an optional [local container registry](https://k3d.io/usage/guides/registries/#using-a-local-registry), which you can use to distribute your custom container images within the cluster. If you're running MacOS, you can use [brew](https://github.com/Homebrew/brew) to install k3d:

```shell
$ brew install k3d
```

Then, create a simple cluster with one server node, one worker node and a container registry:

```shell
$ k3d cluster create my-cluster --servers 1 --agents 1 --registry-create
```

If everything went okay, now you should have a working cluster. You can verify this with:

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

To get the ball rolling, let's write a [trivial Python web application](./app/) with Flask, which we'll deploy to the cluster as a pod:

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

> If you're running MacOS, then k3d-my-cluster-registry might not be a reachable host, because containers are not automatically reachable from the MacOS host. In that case you can just add the host as a new entry in  `/etc/hosts`, i.e. map k3d-my-cluster-registry to 127.0.0.1.

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

## Why settle for one?

Currently our Flask application is running in a single pod. If you delete the pod using `kubectl delete pods/pod-example`, then that particular pod and the application as a whole is gone. Kubernetes neither recreates the pod nor runs multiple replicas of it by default. To do that, you need to use a [ReplicaSet](https://kubernetes.io/docs/concepts/workloads/controllers/replicaset/). ReplicaSets essentially allow you to define how many copies of a pod you want and delegates the details to Kubernetes. Kubernetes (or [controllers](https://kubernetes.io/docs/concepts/architecture/controller/) within Kubernetes to be exact) will monitor how many replicas are running at a given time and if there are too many or too few, it will correct the situation by creating more pods or deleting excess pods.

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

What this definition essentially states is that the ReplicaSet will create three pods, all of which will run our Flask application. It will also assign a label named `app` with a value of `example` to each of our pods, which is a key thing. ReplicaSets work by using these labels to select a set of pods to be the replicas. This is defined with the `matchLabels` attribute. If there aren't enough of pods with matching labels, ReplicaSet will create more. If there are too many, it will delete some.

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

If you take a closer look at a them, you may also notice that some of them have been scheduled to different nodes:

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

## Service please!

Services provide a way to route traffic to multiple pods. Even if new pods are created and old ones removed, the service will still provide a way to always reach the pods.

### Creating a service

There are several service types, the default being ClusterIP. ClusterIP essentially gives you a cluster internal IP, which you can use to reach the service and thus the pods. Note that this IP is only visible _within_ the cluster, i.e. you can't use it to reach the pods from outside the cluster. However, this is fine for our example purposes. So once again, we'll whip up a YAML definition for our service:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: example-service-cluster-ip
spec:
  selector:
    app: example
  ports:
    - port: 80
      targetPort: 5000
```

What this states is that we want a service, which selects all pods with the label `app` being equal to `example`. The service will be available at port 80 and targets the port 5000 on the pods. So let's create the service and then examine it:

```shell
$ kubectl apply -f service-cluster-ip.yml

service/example-service-cluster-ip created

$ kubectl describe svc/service-cluster-ip

Name:              example-service-cluster-ip
Namespace:         default
Labels:            <none>
Annotations:       <none>
Selector:          app=example
Type:              ClusterIP
IP:                10.43.228.111
Port:              <unset>  80/TCP
TargetPort:        5000/TCP
Endpoints:         10.42.0.31:5000,10.42.0.32:5000,10.42.1.20:5000
Session Affinity:  None
Events:            <none>
```

As you can see, we now have an IP we reach the service with. Furthermore, the service lists the IPs of our pods as its endpoints. If you now delete one of the pods, the service will remove the endpoint of that particular pod. Once the ReplicaSet controller creates a replacement pod for the deleted one, the service will add the endpoint of the new pod to its endpoints. Pretty nifty!

### Reaching our service

So the service seemingly tracks the pod IPs, but how do we talk to the service? We can once again utilize a simple pod running busybox. This time, let's start the pod in an interactive mode, so we can run wget multiple times against the service IP:

```shell
$ kubectl run -it busybox --image=busybox --rm --restart=Never

/ # wget -q -O - 10.43.228.111
{"host":"example-replica-set-pslp6"}

/ # wget -q -O - 10.43.228.111
{"host":"example-replica-set-rw7jq"}

/ # wget -q -O - 10.43.228.111
{"host":"example-replica-set-lxzzv"}
```

As you can see, the service is now routing our requests to the different pods. Kubernetes will also create a DNS name for the service, so you can use its name instead of the IP:

```shell
/ # wget -q -O - example-service-cluster-ip
{"host":"example-replica-set-pslp6"}
```

Note that this only if your pod is running in the same namespace as the service. If not, then you have to use a fully qualified name like `example-service-cluster-ip.default.svc.cluster.local`.

## Other service types

Like previously stated, ClusterIP is the default service type. There are [a few others](https://kubernetes.io/docs/concepts/services-networking/service/#publishing-services-service-types), but let's focus on just one alternative type, called NodePort. NodePort will expose a static port on each cluster node and route traffic from this port to a ClusterIP service, which it has created behind the scenes. You can think of it like the previous ClusterIP example, but this time the service is also reachable from outside the cluster through a port on any of the nodes.

### Creating a NodePort

Since k3d runs the nodes as containers, you will want to expose the NodePort port on at least one of the node containers. To do this, delete the current cluster and create a new one, this time mapping the host port 8090 to the port 30080 on the first agent node:

```shell
$ k3d cluster create my-cluster --servers 1 --agents 1 --registry-create -p "8090:30080@agent[0]"
```

Once the cluster is up, we'll create the service again, this time setting the type as NodePort and defining the port to be used on each node:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: example-service-node-port
spec:
  type: NodePort
  selector:
    app: example
  ports:
    - nodePort: 30080
      port: 80
      targetPort: 5000
```

And to bring up the service:

```shell
$ kubectl apply -f service-node-port.yml
```

> Because we created a new cluster, our pods are gone, so the service has no pods to route traffic to. To bring them back up, follow the steps we took previously. You will also need to republish the container image.

If you now check the services, you'll see that the type of the service is now NodePort:

```shell
$ kubectl get svc

NAME                        TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
kubernetes                  ClusterIP   10.43.0.1       <none>        443/TCP        39m
example-service-node-port   NodePort    10.43.240.113   <none>        80:30080/TCP   10m
```

We can once again use a pod to reach the service using the internal cluster IP or the name, but this time we can also do something way better. Remember how we mapped port 8090 on our host to port 30080 on the cluster node? The NodePort service will now route external traffic from that port to the service. We can give it a spin by using curl:

```shell
$ curl localhost:8090

{"host":"example-replica-set-t8ggx"}
```

So we finally have a method of routing traffic from outside the cluster to our pods!

## Deployments

We now have a replicated application, which we can also reach outside of the cluster. However, how should we go about updating our application? What if we want to update the Flask application with a new feature? One way we can do this is by updating the template spec of the container in our ReplicaSet via `kubectl edit rs/my-example-replica-set`. However, editing the ReplicaSet does not by itself trigger a change in the pods it owns. Even if you push a new image to registry and update the ReplicaSet to use it, nothing will automatically happen. Instead, you have to delete a pod. Only then will the ReplicaSet controller spin up a new pod with our new image. To make performing updates like this less awkward, Kubernetes provides a solution called a [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/).

Deployments essentially create and manage ReplicaSets. Once you update a container image defined in the Deployment template, it will create a new ReplicaSet using the new image. Then it will progressively start taking down pods in the old ReplicaSet and bringing up new ones in the new ReplicaSet. This is done by default in a rolling manner, i.e. there is no point in time where there isn't a pod running your container. This way you can update your applications with zero downtime.

### Creating a Deployment

We'll use our example container image again and create a Deployment like this:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: example-deployment
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
        - name: example-pod
          image: k3d-my-cluster-registry:50237/pod-example:0.1
```

Once again, let's create it:

```shell
$ kubectl apply -f deployment.yml
```

You should now be able see that the Deployment created a new ReplicaSet, which brought up three new pods:

```
$ kubectl get rs

NAME                          DESIRED   CURRENT   READY   AGE
example-deployment-d56888b5   3         3         1       3s

$ kubectl get pods

NAME                                READY   STATUS    RESTARTS   AGE
example-deployment-d56888b5-rnrfl   1/1     Running   0          6s
example-deployment-d56888b5-cdvf7   1/1     Running   0          6s
example-deployment-d56888b5-vb4cq   1/1     Running   0          6s
```

### Performing a rolling update

In order to demonstrate a rolling update using our Deployment, we'll need to publish a new image we'll update to, so let's update the example Flask application to also return the IP address of the pod it'll be running in:

```python
import platform
import socket

from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return {"host": platform.node(), "ip": socket.gethostbyname(socket.gethostname())}

```

And publish it as the `0.2` version:

```shell
$ docker build -t k3d-my-cluster-registry:50237/pod-example:0.2 .
$ docker push k3d-my-cluster-registry:50237/pod-example:0.2
```

Now if you update `deployment.yml` to use the new image, and then run `kubectl apply -f deployment.yml`, you'll see a new ReplicaSet, as well as new pods, being created:

```shell
$ kubectl get rs

NAME                           DESIRED   CURRENT   READY   AGE
example-deployment-5b55f4c96   3         3         3       5s
example-deployment-d56888b5    0         0         0       63s

$ kubectl get pods

NAME                                 READY   STATUS        RESTARTS   AGE
example-deployment-5b55f4c96-c86cm   1/1     Running       0          7s
example-deployment-d56888b5-bnqs8    1/1     Terminating   0          65s
example-deployment-5b55f4c96-lkrn5   1/1     Running       0          6s
example-deployment-d56888b5-9gkjf    1/1     Terminating   0          65s
example-deployment-5b55f4c96-l2fk2   1/1     Running       0          4s
example-deployment-d56888b5-kbswh    1/1     Terminating   0          65s
```

We can use wget once again from within the cluster to see that yes, the pods are using our new container image:

```shell
$ wget -q -O - 10.42.1.24:5000

{"host":"example-deployment-5b55f4c96-c86cm","ip":"10.42.1.24"}
```

Once this rollout has completed, the previous ReplicaSet and its pods are gone. You can check the status of the rollout like this:

```shell
$ kubectl rollout status deployment/example-deployment

deployment "example-deployment" successfully rolled out
```

And if you want to, you can even perform a rollback using `kubectl rollout undo deployment/example-deployment`, as Deployments track their rollouts. Very neat!

## Ingress

Finally, let's backtrack to Services for a bit. While the Service with type NodePort worked fine for our toy application, what if you want to expose multiple Services outside the cluster? Or do something a bit more advanced? Perhaps you'd like to expose a single port outside the cluster, receive HTTP requests through that port and route the received requests to different Services within the cluster. Maybe you'd also like to perform TLS termination there for HTTPS . For exactly those purposes, Kubernetes provides a resource type called [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/).

Creating an Ingress by itself does not do anything. You also need an Ingress controller, which monitors the created Ingress resource and you know, actually does the things the resource defines. Luckily for us, k3d comes with a built-in ingress controller using [Traefik](https://doc.traefik.io/traefik/providers/kubernetes-ingress/). However, as k3d runs the cluster nodes in Docker containers, we have to create the cluster in a specific manner, where we map a host port to a port on a load balancer provided by k3d, which sits in front of the server nodes of the cluster:

```shell
$ k3d cluster create my-cluster --servers 1 --agents 1 --registry-create -p "8090:80@loadbalancer"
```

When the cluster is created this way, the port 8090 on the host will reach the port 80 on the load balancer, which serves as the gateway to our Ingress and the cluster.

### Creating an Ingress

Unsurprisingly, our Ingress definition looks pretty familiar:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ingress-example
spec:
  rules:
    - http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: example-service-cluster-ip
                port:
                  number: 80
```

This minimal example should be fairly obvious. Our Ingress will just route all HTTP requests it receives to our previous example of a Service. You could of course perform more complex path based routing to route to multiple Services, but for our learning purposes this is fine. To get our humble little Ingress up and running, let's first bring up our Deployment and Service again, since we recreated the entire cluster and everything was wiped out:

```shell
$ kubectl apply -f deployment.yml

deployment.apps/example-deployment created

$ kubectl apply -f service-cluster-ip.yml

service/example-service-cluster-ip created
```

> These commands assume you've also republished the container images if the container registry was wiped out

Finally, let's create the Ingress itself:

```shell
kubectl apply -f ingress.yml

ingress.networking.k8s.io/ingress-example created
```

Now for the moment of truth, let's try curling our Ingress from outside the cluster:

```shell
$ curl localhost:8090

{"host":"example-deployment-76bcb4bf6c-p5hpg","ip":"10.42.0.7"}
```

And it works! Traffic is flowing from outside the cluster, through the Ingress, all the way to our pods.

## Conclusion

There's quite a lot to unpack here, but let's see if we can summarize all the things we've done. We've created a Kubernetes cluster and deployed our containerized application as a pod. To be more specific, this pod is actually several replicas, all of which are managed by a ReplicaSet. Going even further, this ReplicaSet is maintained by a Deployment, allowing us to perform rolling updates to our pods. In order to route traffic to these ephemeral pods, we created a Service. And to allow traffic to flow from outside the cluster to our Service, we created an Ingress. Whew!
