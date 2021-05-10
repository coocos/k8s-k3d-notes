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
