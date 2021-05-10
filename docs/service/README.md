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
