## Deployments

We now have a replicated application, which we can also reach outside of the cluster. However, how should we go about updating our application? What if we want to update the Flask application with a new feature? One way we can do this is by updating the template spec of the container in our ReplicaSet via `kubectl edit rs/my-example-replica-set`. However, editing the ReplicaSet does not by itself trigger a change in the pods it owns. Even if you push a new image to registry and update the ReplicaSet to use it, nothing will automatically happen. Instead, you have to delete a pod. Only then will the ReplicaSet controller spin up a new pod with our new image. To make performing updates like this less awkward, Kubernetes provides a solution called a [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/).

### How Deployments work

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
