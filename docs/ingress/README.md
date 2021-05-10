## Ingress

Finally, let's backtrack to services for a bit. While the service with type NodePort worked fine for our toy application, what if you want to expose multiple services outside the cluster? Or do something a bit more advanced? Perhaps you'd like to expose a single port outside the cluster, receive HTTP requests through that port and route the received requests to different services within the cluster. Maybe you'd also like to perform TLS termination there for HTTPS . For exactly those purposes, Kubernetes provides a resource type called [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/).

### Ingress controllers

Creating an ingress by itself does not do anything. You also need an ingress controller, which monitors the created ingress resource and you know, actually does the things the resource defines. Luckily for us, k3d comes with a built-in ingress controller using [Traefik](https://doc.traefik.io/traefik/providers/kubernetes-ingress/). However, as k3d runs the cluster nodes in Docker containers, we have to create the cluster in a specific manner, where we map a host port to a port on a load balancer provided by k3d, which sits in front of the server nodes of the cluster:

```shell
$ k3d cluster create my-cluster --servers 1 --agents 1 --registry-create -p "8090:80@loadbalancer"
```

When the cluster is created this way, the port 8090 on the host will reach the port 80 on the load balancer, which serves as the gateway to our ingress and the cluster.

### Creating an Ingress

Unsurprisingly, our ingress definition looks pretty familiar:

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

This minimal example should be fairly obvious. Our ingress will just route all HTTP requests it receives to our example service. You could of course perform more complex path based routing to route to multiple services, but for our learning purposes this is fine. To get our humble little ingress up and running, let's first bring up our service and pods, since we recreated the entire cluster and everything was wiped out:

```shell
$ kubectl apply -f deployment.yml

deployment.apps/example-deployment created

$ kubectl apply -f service-cluster-ip.yml

service/example-service-cluster-ip created
```

> These commands assume you've also republished the container images if the container registry was wiped out

Finally, let's create the ingress itself:

```shell
kubectl apply -f ingress.yml

ingress.networking.k8s.io/ingress-example created
```

Now for the moment of truth, let's try curling our ingress from outside the cluster:

```shell
$ curl localhost:8090

{"host":"example-deployment-76bcb4bf6c-p5hpg","ip":"10.42.0.7"}
```

And it works! Traffic is flowing from outside the cluster, through the ingress, all the way to our pods.

## Conclusion

There's quite a lot to unpack here, but let's see if we can summarize all the things we've done. We've created a Kubernetes cluster and deployed our containerized application as a pod. To be more specific, this pod is actually several replicas, all of which are managed by a ReplicaSet. Going even further, this ReplicaSet is maintained by a Deployment, allowing us to perform rolling updates to our pods. In order to route traffic to these ephemeral pods, we created a Service. And to allow traffic to flow from outside the cluster to our Service, we created an Ingress. Whew!
